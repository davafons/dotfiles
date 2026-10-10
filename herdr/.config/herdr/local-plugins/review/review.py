#!/usr/bin/env python3
"""A persistent CodeDiff pane per source pane/checkout; no agent input or VCS writes."""

import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys

PLUGIN = "david.review"


def request(method, params=None):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(10)
        connection.connect(os.environ["HERDR_SOCKET_PATH"])
        connection.sendall((json.dumps({"id": PLUGIN, "method": method,
                                       "params": params or {}}) + "\n").encode())
        with connection.makefile("rb") as replies:
            reply = json.loads(replies.readline())
    if "error" in reply:
        raise RuntimeError(str(reply["error"]))
    return reply["result"]


def repository(cwd):
    if not cwd:
        raise RuntimeError("The source pane has no working directory.")
    path = Path(cwd).expanduser().resolve()
    for root in (path, *path.parents):
        if (root / ".jj").exists():
            if not (root / ".git").exists():
                raise RuntimeError("CodeDiff currently needs a Git-backed jj checkout.")
            return "jj", root
        if (root / ".git").exists():
            return "git", root
    raise RuntimeError("Open review from a pane inside a jj or Git checkout.")


def state_dir():
    path = Path(os.environ["HERDR_PLUGIN_STATE_DIR"])
    path.mkdir(parents=True, exist_ok=True)
    return path


def records():
    for path in state_dir().glob("review-*.json"):
        try:
            record = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        if record.get("herdr_socket") == os.environ["HERDR_SOCKET_PATH"]:
            yield path, record


def write_record(path, record):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(record) + "\n")
    temporary.chmod(0o600)
    temporary.replace(path)


def pane(pane_id):
    try:
        return request("pane.get", {"pane_id": pane_id})["pane"]
    except RuntimeError as error:
        if any(code in str(error) for code in ("pane_not_found", "not_found")):
            return None
        raise


def remote(record, expression):
    result = subprocess.run([shutil.which("nvim") or "nvim", "--server", record["nvim_socket"],
                             "--remote-expr", expression], capture_output=True, text=True, timeout=10)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "The review editor is not responding.")
    return result.stdout.strip()


def return_to_source(record):
    if not pane(record["source_pane"]):
        raise RuntimeError("The source pane has closed. The review editor is still available.")
    request("pane.focus", {"pane_id": record["source_pane"]})


def toggle():
    context = json.loads(os.environ.get("HERDR_PLUGIN_CONTEXT_JSON", "{}"))
    # Explicit action context wins over this process's inherited caller IDs.
    source_id = context.get("focused_pane_id") or os.environ.get("HERDR_PANE_ID")
    if not source_id:
        raise RuntimeError("Invoke review from a specific pane.")
    for _, record in records():
        if record.get("review_pane") == source_id:
            return_to_source(record)
            return
    source = pane(source_id)
    if not source:
        raise RuntimeError("The source pane has closed.")
    kind, root = repository(source.get("foreground_cwd") or source.get("cwd"))
    key = hashlib.sha256((os.environ["HERDR_SOCKET_PATH"] + source_id + str(root)).encode()).hexdigest()[:16]
    path = state_dir() / ("review-" + key + ".json")
    with path.with_suffix(".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if path.exists():
            record = json.loads(path.read_text())
            existing = pane(record["review_pane"]) if record.get("review_pane") else None
            if existing:
                # Never send keystrokes to a reused pane or restart an occupied editor.
                owner = remote(record, "luaeval('vim.env.HERDR_REVIEW_CONTEXT_PATH')")
                if owner != str(path):
                    raise RuntimeError("The saved review socket does not belong to this review.")
                remote(record, "luaeval(\"require('config.herdr_review').open()\")")
                request("pane.focus", {"pane_id": existing["pane_id"]})
                return
        sockets = Path("/tmp") / ("herdr-review-" + str(os.getuid()))
        sockets.mkdir(mode=0o700, exist_ok=True)
        if sockets.is_symlink() or sockets.stat().st_uid != os.getuid():
            raise RuntimeError("The review socket directory is not owned by this user.")
        sockets.chmod(0o700)
        record = {"herdr_socket": os.environ["HERDR_SOCKET_PATH"], "source_pane": source_id,
                  "source_agent": source.get("agent"), "source_session": source.get("agent_session"),
                  "root": str(root), "kind": kind, "nvim_socket": str(sockets / (key + ".sock")),
                  "launcher": str(Path(__file__).resolve()), "review_pane": None}
        write_record(path, record)
        layout = request("pane.layout", {"pane_id": source_id})
        rect = next((entry.get("rect", {}) for entry in layout["layout"].get("panes", [])
                     if entry.get("pane_id") == source_id), {})
        direction = "right" if rect.get("width", 120) >= 120 else "down"
        opened = request("plugin.pane.open", {"plugin_id": PLUGIN, "entrypoint": "review",
                         "target_pane_id": source_id,
                         "direction": direction, "focus": True,
                         "env": {"HERDR_REVIEW_CONTEXT_PATH": str(path)}})
        record["review_pane"] = opened["plugin_pane"]["pane"]["pane_id"]
        write_record(path, record)


def ui():
    path = Path(os.environ["HERDR_REVIEW_CONTEXT_PATH"])
    record = json.loads(path.read_text())
    # The pane can start before plugin.pane.open returns its ID.
    os.chdir(record["root"])
    address = Path(record["nvim_socket"])
    if address.exists():
        address.unlink()  # Only a closed previous review's socket is reused here.
    nvim = shutil.which("nvim")
    if not nvim:
        raise RuntimeError("nvim was not found on PATH.")
    os.execv(nvim, [nvim, "--listen", str(address), "-c",
                   "lua require('config.herdr_review').setup()"])


def main():
    if os.environ.get("HERDR_ENV") != "1" and not (os.environ.get("HERDR_PLUGIN_CONTEXT_JSON")
                                                and os.environ.get("HERDR_SOCKET_PATH")):
        raise RuntimeError("Review must run inside Herdr.")
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "toggle":
        toggle()
    elif command == "ui":
        ui()
    elif command == "return":
        return_to_source(json.loads(Path(os.environ["HERDR_REVIEW_CONTEXT_PATH"]).read_text()))
    else:
        raise RuntimeError("Use toggle, ui or return.")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, ValueError, subprocess.TimeoutExpired) as error:
        print("Checkout review: " + str(error), file=sys.stderr)
        sys.exit(1)
