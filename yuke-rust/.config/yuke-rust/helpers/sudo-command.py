#!/usr/bin/env python3
"""Run one approved sudo command. Keep askpass bytes off command stdin and disk."""
import json
import os
import pathlib
import resource
import selectors
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time

LIMIT = 24 * 1024


class Output:
    """Redact the password before a stream enters the bounded result buffer."""

    def __init__(self, password):
        self.secrets = [password.encode("utf-8")]
        self.pending = b""
        self.kept = bytearray()
        self.dropped = 0

    def feed(self, data, final=False):
        data = self.pending + data
        for secret in self.secrets:
            data = data.replace(secret, b"[REDACTED]")
        end = len(data) if final else max(0, len(data) - len(self.secrets[0]) + 1)
        safe, self.pending = data[:end], data[end:]
        room = max(0, LIMIT - len(self.kept))
        self.kept.extend(safe[:room])
        self.dropped += max(0, len(safe) - room)

    def text(self):
        self.feed(b"", final=True)
        text = self.kept.decode("utf-8", errors="replace")
        if self.dropped:
            text += "\n[Output truncated; no log was saved.]"
        return text


def read_message(buffer_borrow, limit, stopped=None):
    """Read one bounded private stdin record. A stop cancels an incomplete record."""
    with selectors.DefaultSelector() as selector:
        selector.register(sys.stdin.fileno(), selectors.EVENT_READ)
        while b"\n" not in buffer_borrow:
            if len(buffer_borrow) > limit:
                raise ValueError("private message too large")
            if stopped is not None and stopped.is_set():
                return b""
            if not selector.select(0.1):
                continue
            chunk = os.read(sys.stdin.fileno(), 8192)
            if not chunk:
                break
            buffer_borrow.extend(chunk)
    end = buffer_borrow.find(b"\n")
    end = len(buffer_borrow) if end < 0 else end + 1
    if end > limit:
        raise ValueError("private message too large")
    message = bytes(buffer_borrow[:end])
    del buffer_borrow[:end]
    return message


def askpass():
    """Send the password only to sudo's private askpass pipe."""
    with socket.socket(socket.AF_UNIX) as connection:
        connection.connect(os.environ["YUKE_SUDO_SOCKET"])
        data = bytearray()
        while chunk := connection.recv(4096):
            data.extend(chunk)
        if not data:
            return 1
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()
    return 0


def run(request, sudo="/usr/bin/sudo", password_buffer=None):
    """Return bounded output. The caller owns the request and result."""
    if password_buffer is None:
        password_buffer = bytearray()
    password = request["password"]
    if not isinstance(password, str) or not password or any(c in password for c in "\r\n\x00"):
        raise ValueError("invalid password")
    argv = request["argv"]
    if not isinstance(argv, list) or not argv or not isinstance(argv[0], str) or not argv[0].startswith("/"):
        raise ValueError("invalid command")
    if any(not isinstance(arg, str) or "\x00" in arg for arg in argv):
        raise ValueError("invalid argument")
    timeout = request["timeout_ms"]
    if type(timeout) is not int or not 1 <= timeout <= 600000:
        raise ValueError("invalid deadline")
    streams = [Output(password), Output(password)]
    output_lock = threading.Lock()
    canceled = threading.Event()
    with tempfile.TemporaryDirectory(prefix="yuke-sudo-") as directory:
        os.chmod(directory, 0o700)
        address = str(pathlib.Path(directory) / "password.sock")
        helper = pathlib.Path(directory) / "askpass"
        helper.write_text("#!/bin/sh\nexec " + shlex.quote(sys.executable) + " " + shlex.quote(str(pathlib.Path(__file__).resolve())) + " --askpass\n")
        helper.chmod(0o700)
        with socket.socket(socket.AF_UNIX) as server:
            server.bind(address)
            os.chmod(address, 0o600)
            server.listen(1)
            server.settimeout(0.1)
            stopped = threading.Event()

            def serve():
                current = password
                attempt = 1
                while not stopped.is_set():
                    try:
                        connection, _ = server.accept()
                    except socket.timeout:
                        continue
                    except OSError:
                        break
                    with connection:
                        connection.settimeout(1)
                        if attempt > 1:
                            sys.stdout.write(json.dumps({"type": "password", "attempt": attempt}) + "\n")
                            sys.stdout.flush()
                            try:
                                reply = json.loads(read_message(password_buffer, 32768, stopped))
                                current = reply["password"]
                                if not isinstance(current, str) or len(current) > 4096 or any(c in current for c in "\r\n\x00"):
                                    current = ""
                            except (ValueError, KeyError, TypeError):
                                current = ""
                            if stopped.is_set():
                                return
                            if not current:
                                canceled.set()
                                return
                            with output_lock:
                                for stream in streams:
                                    stream.secrets.append(current.encode("utf-8"))
                                    stream.secrets.sort(key=len, reverse=True)
                        try:
                            connection.sendall(current.encode("utf-8") + b"\n")
                        except OSError:
                            return
                    current = ""
                    attempt += 1

            worker = threading.Thread(target=serve, daemon=True)
            worker.start()
            child = None
            timed_out = False
            try:
                environment = os.environ.copy()
                environment["SUDO_ASKPASS"] = str(helper)
                environment["YUKE_SUDO_SOCKET"] = address
                child = subprocess.Popen([sudo, "-k", "-A", "--", *argv], stdin=subprocess.DEVNULL,
                                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment)
                deadline = time.monotonic() + timeout / 1000
                with selectors.DefaultSelector() as selector:
                    for index, pipe in enumerate((child.stdout, child.stderr)):
                        selector.register(pipe, selectors.EVENT_READ, index)
                    while selector.get_map():
                        if time.monotonic() >= deadline:
                            timed_out = True
                            break
                        for key, _ in selector.select(min(0.1, max(0, deadline - time.monotonic()))):
                            chunk = os.read(key.fileobj.fileno(), 8192)
                            if chunk:
                                with output_lock:
                                    streams[key.data].feed(chunk)
                            else:
                                selector.unregister(key.fileobj)
                    if not timed_out:
                        try:
                            child.wait(timeout=max(0.001, deadline - time.monotonic()))
                        except subprocess.TimeoutExpired:
                            timed_out = True
            finally:
                stopped.set()
                worker.join(timeout=1.2)
                if child is not None:
                    try:
                        if child.poll() is None:
                            child.terminate()
                            try:
                                child.wait(timeout=2)
                            except subprocess.TimeoutExpired:
                                child.kill()
                                child.wait(timeout=2)
                    finally:
                        child.stdout.close()
                        child.stderr.close()
            return {"stdout": streams[0].text(), "stderr": streams[1].text(),
                    "exit_code": child.returncode if child.returncode >= 0 else None,
                    "signal": -child.returncode if child.returncode < 0 else None,
                    "timed_out": timed_out, "canceled": canceled.is_set()}


def resolve_command(command_borrow):
    """Resolve one literal argv without running it. Reject shell expansion and sudo options."""
    if len(command_borrow) > 65536 or any(ord(char) < 32 or ord(char) == 127 for char in command_borrow):
        raise ValueError("Use one command line without control codes.")
    parser = shlex.shlex(command_borrow, posix=True, punctuation_chars=True)
    parser.whitespace_split = True
    parser.commenters = ""
    argv = list(parser)
    if not argv or argv[0].startswith("-") or len(argv) > 128:
        raise ValueError("Use !sudo executable arguments. Sudo options are not supported.")
    for argument in argv:
        if argument and all(char in "();<>|&" for char in argument):
            raise ValueError("Shell operators are not supported after !sudo. Approve an explicit shell with -c for a root script.")
    script = 2 if len(argv) >= 3 and os.path.basename(argv[0]) in {"sh", "bash", "zsh", "fish", "dash"} and argv[1] == "-c" else None
    for index, argument in enumerate(argv):
        if index != script and any(char in argument for char in "$`*?~"):
            raise ValueError("Shell expansion is not supported after !sudo. Use literal arguments, or an explicit shell with -c.")
    executable = shutil.which(argv[0])
    if not executable:
        raise ValueError("The sudo executable was not found in PATH.")
    argv[0] = os.path.abspath(executable)
    if os.path.basename(argv[0]) == "sudo":
        raise ValueError("Do not nest sudo commands.")
    return argv


def main():
    """Read private stdin. Never report request data or an exception's contents."""
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    if len(sys.argv) == 3 and sys.argv[1] == "--resolve":
        try:
            sys.stdout.write(json.dumps(resolve_command(sys.argv[2])) + "\n")
            return 0
        except ValueError as error:
            sys.stderr.write(str(error) + "\n")
            return 2
    if sys.argv[1:] == ["--askpass"]:
        return askpass()
    os.umask(0o077)

    def interrupted(_signal, _frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupted)
    try:
        incoming = bytearray()
        request = json.loads(read_message(incoming, 1024 * 1024))
        result = run(request, password_buffer=incoming)
        sys.stdout.write(json.dumps({"type": "result", "result": result}) + "\n")
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception:
        sys.stderr.write("Sudo helper failed. No request data was logged.\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
