#!/usr/bin/env python3
"""Check live work activity through a private Herdr socket and detached Yuke terminal."""
import argparse
import json
import os
from pathlib import Path
import shlex
import shutil
import socketserver
import subprocess
import tempfile
import threading
import time
import uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    args = parser.parse_args()
    binary = args.binary.resolve(strict=True)
    root = Path(tempfile.mkdtemp(prefix="yw-", dir="/tmp")).resolve()
    root.chmod(0o700)
    profile = root / "config/yuke"
    source = Path(__file__).resolve().parents[1] / ".config/yuke"
    shutil.copytree(source, profile, ignore=shutil.ignore_patterns("providers.json*", "*.key", ".env", "__pycache__", "yuke.d.ts", "yuke-modules.d.ts", "yuke.jsconfig.json"))
    for name in ("home", "work", "data", "state", "cache"):
        (root / name).mkdir()
    (profile / "providers.json").write_text(json.dumps({"providers": [{"id": "work-test", "base_url": "http://127.0.0.1:1/v1", "endpoints": [{"protocol": "openai_chat"}], "models": [{"id": "model", "upstream_id": "model", "flags": {"supports_tools": True}}]}]}))
    (profile / "providers.json").chmod(0o600)
    foreign = "1" * 32
    reported = "working"
    calls = []

    class Herdr(socketserver.StreamRequestHandler):
        def handle(self):
            request = json.loads(self.rfile.readline())
            calls.append(request["method"])
            result = {"type": "ok"}
            if request["method"] == "pane.list":
                result = {"type": "pane_list", "panes": [{"pane_id": "foreign", "agent": "yuke", "agent_status": reported, "tokens": {"yuke_session_id": foreign}}]}
            self.wfile.write((json.dumps({"id": request["id"], "result": result}) + "\n").encode())

    server = socketserver.ThreadingUnixStreamServer(str(root / "herdr.sock"), Herdr)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    env = {"PATH": os.environ["PATH"], "HOME": str(root / "home"), "TERM": "xterm-256color", "YUKE_APPNAME": "yuke", "HERDR_ENV": "1", "HERDR_SOCKET_PATH": str(root / "herdr.sock"), "HERDR_PANE_ID": "fixture"}
    for name in ("config", "data", "state", "cache"):
        env["XDG_" + name.upper() + "_HOME"] = str(root / name)
    database = root / "state/yuke/work/work.sqlite3"
    task = {"action": "task", "root": str(root / "work"), "session": foreign, "title": "LIVE_WORK_FIXTURE", "status": "now", "notes": "Keep this task now when the linked agent becomes idle."}
    subprocess.run(["python3", str(profile / "plugins/project-work-store.py"), str(database), json.dumps(task)], env=env, check=True, capture_output=True)
    socket = "yuke-work-" + uuid.uuid4().hex[:10]
    captures = []

    def mux(*args):
        return subprocess.check_output(["tmux", "-L", socket, *args], text=True)

    def screen():
        return mux("capture-pane", "-p", "-t", "work")

    def wait(condition, label):
        end = time.monotonic() + 15
        while time.monotonic() < end:
            if condition():
                captures.append(label + "\n" + screen())
                return
            time.sleep(0.05)
        raise AssertionError(label + "\n" + screen())

    def task_read():
        result = subprocess.check_output(["python3", str(profile / "plugins/project-work-store.py"), str(database), json.dumps({"action": "list", "root": str(root / "work")})], env=env, text=True)
        return json.loads(result)["tasks"][0]

    try:
        command = shlex.join(["env", "-i", *(f"{k}={v}" for k, v in env.items()), str(binary)])
        mux("new-session", "-d", "-x", "160", "-y", "45", "-s", "work", "-n", "Agent Tests work activity", "-c", str(root / "work"), command)
        wait(lambda: "Project tasks" in screen() and "Search chats" in screen(), "dashboard actions loaded after all plugins")
        mux("send-keys", "-t", "work", "w")
        wait(lambda: "LIVE_WORK_FIXTURE" in screen() and "working · Herdr" in screen(), "reported working activity")
        before = screen()
        wait(lambda: screen() != before, "moving indicator")
        reported = "idle"
        wait(lambda: "idle · Herdr" in screen(), "remote idle updates live")
        assert task_read()["status"] == "now", "idle marked the task done"
        reported = "blocked"
        wait(lambda: "blocked · Herdr" in screen(), "remote blocked updates live")
        mux("send-keys", "-t", "work", "Escape")
        wait(lambda: "Work ·" not in screen(), "work dialog closed")
        count = calls.count("pane.list")
        time.sleep(1.4)
        assert calls.count("pane.list") == count, "closed dialog kept polling"
        print(json.dumps({"working": True, "animation": True, "idle_preserves_status": True, "blocked": True, "close_stops_poll": True, "artifacts": str(root)}, indent=2))
    finally:
        (root / "captures.txt").write_text("\n".join(captures))
        subprocess.run(["tmux", "-L", socket, "kill-server"], capture_output=True)
        server.shutdown()
        server.server_close()
        print("Work activity artifacts:", root)


if __name__ == "__main__":
    main()
