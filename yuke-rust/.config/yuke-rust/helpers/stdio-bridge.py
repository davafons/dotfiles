#!/usr/bin/env python3
"""Carry subprocess stdin and output over one private local socket."""
import codecs
import json
import os
from pathlib import Path
import resource
import selectors
import signal
import socket
import subprocess
import sys


def run(path):
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    os.umask(0o077)
    child = None
    address = Path(path)
    try:
        with socket.socket(socket.AF_UNIX) as server:
            server.bind(str(address))
            server.listen(1)
            server.settimeout(10)
            connection, _ = server.accept()
            with connection, connection.makefile('rb', buffering=0) as incoming:
                line = incoming.readline(65537)
                if len(line) > 65536:
                    raise ValueError('command record too large')
                command = json.loads(line)
                child = subprocess.Popen(command['argv'], cwd=command['cwd'], stdin=subprocess.PIPE,
                                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                connection.sendall(b'{"type":"started"}\n')
                with selectors.DefaultSelector() as selector:
                    selector.register(connection, selectors.EVENT_READ, 'stdin')
                    selector.register(child.stdout, selectors.EVENT_READ, 'stdout')
                    selector.register(child.stderr, selectors.EVENT_READ, 'stderr')
                    buffered = bytearray()
                    decoders = {name: codecs.getincrementaldecoder('utf-8')(errors='replace') for name in ('stdout', 'stderr')}
                    while len(selector.get_map()) > 1:
                        for key, _ in selector.select():
                            if key.data == 'stdin':
                                data = os.read(connection.fileno(), 8192)
                                if not data:
                                    return
                                buffered.extend(data)
                                if len(buffered) > 1024 * 1024:
                                    raise ValueError('stdin record too large')
                                while b'\n' in buffered:
                                    line, _, rest = buffered.partition(b'\n')
                                    buffered[:] = rest
                                    message = json.loads(line)
                                    if message['type'] != 'stdin' or not isinstance(message['text'], str):
                                        raise ValueError('invalid stdin record')
                                    child.stdin.write(message['text'].encode())
                                    child.stdin.flush()
                            else:
                                data = os.read(key.fileobj.fileno(), 8192)
                                text = decoders[key.data].decode(data, final=not data)
                                if text:
                                    connection.sendall((json.dumps({'type': key.data, 'text': text}) + '\n').encode())
                                if not data:
                                    selector.unregister(key.fileobj)
                    code = child.wait()
                    connection.sendall((json.dumps({'type': 'exit', 'code': code}) + '\n').encode())
    finally:
        if child is not None:
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
            for pipe in (child.stdin, child.stdout, child.stderr):
                pipe.close()
        address.unlink(missing_ok=True)


def stop(_signal, _frame):
    raise KeyboardInterrupt


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, stop)
    try:
        run(sys.argv[1])
    except (KeyboardInterrupt, BrokenPipeError, ConnectionResetError):
        sys.exit(130)
    except Exception:
        # The private records can contain passwords.
        sys.stderr.write('The private subprocess bridge failed.\n')
        sys.exit(1)
