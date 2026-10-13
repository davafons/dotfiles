#!/usr/bin/env python3
"""Herdr-owned Neovim sessions with one attached UI per checkout/workspace."""

from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import time

PLUGIN = "david.code"
ROOT = Path(__file__).resolve().parent


def request(method, params=None):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(10)
        connection.connect(os.environ["HERDR_SOCKET_PATH"])
        connection.sendall((json.dumps({"id": PLUGIN, "method": method, "params": params or {}}) + "\n").encode())
        with connection.makefile("rb") as replies:
            reply = json.loads(replies.readline())
    if "error" in reply:
        raise RuntimeError(str(reply["error"]))
    return reply["result"]


def nvim():
    executable = shutil.which("nvim")
    if not executable:
        raise RuntimeError("nvim was not found on PATH.")
    return executable


def repository(cwd):
    if cwd:
        path = Path(cwd).expanduser().resolve()
        for root in (path, *path.parents):
            if (root / ".jj").exists():
                return "jj", root
            if (root / ".git").exists():
                return "git", root
    raise RuntimeError("Open Code from a pane inside a jj or Git checkout.")


def state_dir():
    path = Path(os.environ["HERDR_PLUGIN_STATE_DIR"])
    path.mkdir(parents=True, exist_ok=True)
    return path


def record_key(address, workspace, root):
    return hashlib.sha256(json.dumps([address, workspace, str(root)]).encode()).hexdigest()[:20]


@contextmanager
def locked(path):
    with path.with_suffix(".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def write_record(path, record):
    temporary = path.with_suffix(".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w") as file:
        os.fchmod(file.fileno(), 0o600)
        file.write(json.dumps(record) + "\n")
    temporary.replace(path)


def update(path, expected_generation=None, **fields):
    with locked(path):
        record = json.loads(path.read_text())
        generation = record.get("view_generation", 0)
        if expected_generation is not None and generation != expected_generation:
            return None
        if "view" in fields:
            fields["view_generation"] = generation + 1
        record.update(fields)
        write_record(path, record)
        return record


def records():
    for path in state_dir().glob("code-*.json"):
        try:
            record = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        if record.get("herdr_socket") == os.environ["HERDR_SOCKET_PATH"]:
            yield path, record


def pane(pane_id):
    try:
        return request("pane.get", {"pane_id": pane_id})["pane"]
    except RuntimeError as error:
        if "pane_not_found" in str(error) or "not_found" in str(error):
            return None
        raise


def pin_tabs():
    with locked(state_dir() / "tab-order.json"):
        saved = list(records())
        if not saved:
            return
        snapshot = request("session.snapshot")["snapshot"]
        panes = {item["pane_id"]: item for item in snapshot["panes"]}
        owned = set()
        for _, record in saved:
            editor = panes.get(record.get("editor_pane"))
            if not editor or editor.get("terminal_id") != record.get("editor_terminal"):
                continue
            if editor["workspace_id"] != record["workspace_id"]:
                continue
            if editor.get("tokens", {}).get("pane_kind") != "editor":
                request("tab.rename", {"tab_id": editor["tab_id"], "label": "Code"})
                request("pane.report_metadata", {"pane_id": editor["pane_id"], "source": "plugin:" + PLUGIN,
                                                "tokens": {"pane_kind": "editor"}})
            owned.add(editor["tab_id"])
        workspaces = {}
        for tab in snapshot["tabs"]:
            workspaces.setdefault(tab["workspace_id"], []).append(tab["tab_id"])
        for current in workspaces.values():
            code_tabs = [tab for tab in current if tab in owned]
            for offset, tab_id in enumerate(reversed(code_tabs)):
                index = len(current) - offset - 1
                position = current.index(tab_id)
                if position != index:
                    moved = request("tab.move", {"tab_id": tab_id, "insert_index": index + (position < index)})
                    current = [tab["tab_id"] for tab in moved["tabs"]]


def target_of(source):
    if not source.get("agent"):
        return None
    return {"pane_id": source["pane_id"], "agent": source["agent"],
            "terminal_id": source.get("terminal_id"), "session": source.get("agent_session"),
            "yuke_session_id": source.get("tokens", {}).get("yuke_session_id"),
            "number": source.get("tokens", {}).get("shortcut_number"),
            "summary": source.get("tokens", {}).get("summary") or source.get("terminal_title_stripped")}


def set_target(path, pane_id, expected=None):
    selected = pane(pane_id)
    target = target_of(selected) if selected else None
    if not target:
        raise RuntimeError("That agent has gone; choose another target.")
    if expected is not None and any(target.get(field) != expected.get(field)
           for field in ("pane_id", "agent", "terminal_id", "session", "yuke_session_id")):
        raise RuntimeError("The selected agent or session changed. Choose again; your tags are kept.")
    return update(path, target=target)


def remote(record, code):
    expression = "luaeval(" + json.dumps("(function() " + code + " end)()") + ")"
    result = subprocess.run([nvim(), "--headless", "--server", record["nvim_socket"], "--remote-expr", expression],
                            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=10)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "The Code editor is not responding.")
    return result.stdout.strip()


def wait(condition, label, seconds=12):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        value = condition()
        if value:
            return value
        time.sleep(.1)
    raise RuntimeError("Timed out waiting for " + label + ".")


def ready(record, path):
    try:
        return remote(record, "return require('herdr-code').context_path") == str(path)
    except (RuntimeError, subprocess.TimeoutExpired):
        return False


def ensure(source):
    nvim()
    kind, root = repository(source.get("foreground_cwd") or source.get("cwd"))
    key = record_key(os.environ["HERDR_SOCKET_PATH"], source["workspace_id"], root)
    path = state_dir() / ("code-" + key + ".json")
    with locked(path):
        record = json.loads(path.read_text()) if path.exists() else None
        existing = pane(record["editor_pane"]) if record and record.get("editor_pane") else None
        if existing and existing.get("terminal_id") != record.get("editor_terminal"):
            raise RuntimeError("The saved Code pane has a different owner; no input was sent.")
        if not existing:
            sockets = Path("/tmp") / ("herdr-code-" + str(os.getuid()))
            sockets.mkdir(mode=0o700, exist_ok=True)
            if sockets.is_symlink() or sockets.stat().st_uid != os.getuid():
                raise RuntimeError("The Code socket directory is not owned by this user.")
            sockets.chmod(0o700)
            record = {"herdr_socket": os.environ["HERDR_SOCKET_PATH"], "workspace_id": source["workspace_id"],
                      "root": str(root), "kind": kind, "source_pane": source["pane_id"],
                      "target": target_of(source), "nvim_socket": str(sockets / (key + ".sock")),
                      "launcher": str(Path(__file__).resolve()), "editor_pane": None,
                      "view": "hidden", "view_generation": (record or {}).get("view_generation", 0) + 1,
                      "recovery": str(path.with_suffix(".recovery"))}
            write_record(path, record)
            opened = request("plugin.pane.open", {"plugin_id": PLUGIN, "entrypoint": "code",
                             "workspace_id": source["workspace_id"], "cwd": str(root),
                             "focus": False, "env": {"HERDR_CODE_CONTEXT_PATH": str(path)}})
            editor = opened["plugin_pane"]["pane"]
            record.update(editor_pane=editor["pane_id"], editor_terminal=editor["terminal_id"])
            write_record(path, record)
            request("tab.rename", {"tab_id": editor["tab_id"], "label": "Code"})
        record["source_pane"] = source["pane_id"]
        write_record(path, record)
    pin_tabs()
    wait(lambda: ready(record, path), "the checkout editor; see " + str(path.with_suffix(".log")))
    remote(record, "require('herdr-code').refresh_context(); return true")
    return path, record


def return_to_source(path):
    record = json.loads(path.read_text())
    if not pane(record["source_pane"]):
        raise RuntimeError("The source pane has closed. Code and unsaved edits are still available.")
    update(path, view="hidden")
    request("pane.focus", {"pane_id": record["source_pane"]})


def show_tab(path, changes=False):
    record = update(path, view="tab")
    pin_tabs()
    request("pane.focus", {"pane_id": record["editor_pane"]})
    if changes:
        wait(lambda: remote(record, "return #vim.api.nvim_list_uis()") == "1", "the Code view to attach")
        remote(record, "require('herdr-code').changes(); return true")


def show_overlay(path):
    record = json.loads(path.read_text())
    if record["view"] == "overlay":
        return_to_source(path)
        return
    record = update(path, view="overlay")
    generation = record["view_generation"]
    try:
        wait(lambda: json.loads(path.read_text()).get("view_generation", 0) != generation
             or remote(record, "return #vim.api.nvim_list_uis()") == "0", "the Code tab to detach")
        if json.loads(path.read_text()).get("view_generation", 0) != generation:
            return
        request("pane.focus", {"pane_id": record["source_pane"]})
        request("plugin.pane.open", {"plugin_id": PLUGIN, "entrypoint": "overlay", "focus": True,
                "cwd": record["root"], "env": {"HERDR_CODE_CONTEXT_PATH": str(path), "HERDR_CODE_VIEW_GENERATION": str(generation)}})
    except Exception:
        update(path, expected_generation=generation, view="hidden")
        raise


def action(command):
    context = json.loads(os.environ.get("HERDR_PLUGIN_CONTEXT_JSON", "{}"))
    source_id = context.get("focused_pane_id") or os.environ.get("HERDR_PANE_ID")
    if not source_id:
        raise RuntimeError("Invoke Code from a specific pane.")
    for path, record in records():
        if record.get("editor_pane") == source_id:
            if command == "toggle":
                return_to_source(path)
            elif command == "overlay":
                show_overlay(path)
            else:
                show_tab(path, changes=True)
            return
    source = pane(source_id)
    if not source:
        raise RuntimeError("The source pane has closed.")
    path, _ = ensure(source)
    if command == "overlay":
        show_overlay(path)
    else:
        show_tab(path, changes=command == "changes")


def sync():
    focused = request("session.snapshot")["snapshot"]["focused_pane_id"]
    for path, record in records():
        if record.get("editor_pane") == focused and record["view"] == "hidden":
            update(path, expected_generation=record.get("view_generation", 0), view="tab")
    pin_tabs()


def stop_child(child):
    if child and child.poll() is None:
        child.terminate()
        try:
            child.wait(timeout=3)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()


def run_surface(path, daemon=None):
    stopping = False

    def stop(_signal, _frame):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGHUP, stop)
    record = json.loads(path.read_text())
    surface = "tab" if daemon else "overlay"
    generation = int(os.environ.get("HERDR_CODE_VIEW_GENERATION", record.get("view_generation", 0)))
    client_generation = None
    client = None
    try:
        while not stopping and (daemon is None or daemon.poll() is None):
            record = json.loads(path.read_text())
            visible = record["view"] == surface and (surface == "tab" or record.get("view_generation", 0) == generation)
            if client and client.poll() is not None:
                client = None
                if surface == "overlay":
                    break
                if update(path, expected_generation=client_generation, view="hidden") is not None:
                    visible = False
            if not visible:
                stop_child(client)
                client = None
                if surface == "overlay":
                    break
            elif client is None and remote(record, "return #vim.api.nvim_list_uis()") == "0":
                client = subprocess.Popen([nvim(), "--server", record["nvim_socket"], "--remote-ui"])
                client_generation = record.get("view_generation", 0)
            time.sleep(.15)
    finally:
        stop_child(client)
        if surface == "overlay":
            update(path, expected_generation=generation, view="hidden")


def host(path):
    record = json.loads(path.read_text())
    address = Path(record["nvim_socket"])
    if address.exists():
        address.unlink()
    environment = dict(os.environ, HERDR_CODE_PLUGIN_ROOT=str(ROOT))
    environment.pop("HERDR_PLUGIN_CONTEXT_JSON", None)
    daemon = None
    lifetime_read, lifetime_write = os.pipe()
    environment["HERDR_CODE_LIFETIME_FD"] = str(lifetime_read)
    with path.with_suffix(".log").open("w") as log:
        os.chmod(log.name, 0o600)
        try:
            daemon = subprocess.Popen([nvim(), "--headless", "--listen", str(address),
                        "-c", "lua vim.opt.rtp:append(vim.env.HERDR_CODE_PLUGIN_ROOT); require('herdr-code').setup()"],
                        cwd=record["root"], env=environment, stdin=subprocess.DEVNULL,
                        stdout=log, stderr=log, start_new_session=True, pass_fds=(lifetime_read,))
            os.close(lifetime_read)
            lifetime_read = None
            update(path, daemon_pid=daemon.pid, host_pid=os.getpid())

            def started():
                if daemon.poll() is not None:
                    raise RuntimeError("Neovim exited during startup; see " + str(path.with_suffix('.log')))
                return ready(record, path)
            wait(started, "Neovim startup")
            run_surface(path, daemon)
        except Exception as error:
            log.write("\nCode host: " + repr(error) + "\n")
            log.flush()
            raise
        finally:
            if lifetime_read is not None:
                os.close(lifetime_read)
            os.close(lifetime_write)
            if daemon and daemon.poll() is None:
                try:
                    daemon.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    log.write("Neovim did not stop after its owner closed the lifetime pipe.\n")
                    log.flush()
            stop_child(daemon)
            if address.exists():
                address.unlink()


def main():
    if not os.environ.get("HERDR_SOCKET_PATH"):
        raise RuntimeError("Code must run inside Herdr.")
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command in ("toggle", "overlay", "changes"):
        action(command)
    elif command == "sync":
        sync()
    elif command in ("pin", "pin-current"):
        pin_tabs()
    else:
        path = Path(os.environ["HERDR_CODE_CONTEXT_PATH"])
        if command == "host":
            host(path)
        elif command == "ui-overlay":
            run_surface(path)
        elif command == "return":
            return_to_source(path)
        elif command == "tab":
            show_tab(path)
        elif command == "target":
            expected = target_of(json.loads(sys.argv[3])) if len(sys.argv) > 3 else None
            set_target(path, sys.argv[2], expected)
        else:
            raise RuntimeError("Unknown Code command: " + command)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, ValueError, subprocess.TimeoutExpired) as error:
        print("Workspace Code: " + str(error), file=sys.stderr)
        sys.exit(1)
