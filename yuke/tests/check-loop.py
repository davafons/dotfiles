#!/usr/bin/env python3
"""Verify native loop delivery, pause, stop, and reload in a private terminal and local provider."""
import argparse
import http.server
import json
import os
from pathlib import Path
import shlex
import shutil
import sqlite3
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
    root = Path(tempfile.mkdtemp(prefix="yuke-loop-check-"))
    root.chmod(0o700)
    profile = root / "config/yuke"
    profile.mkdir(parents=True)
    for name in ("home", "work", "data", "state", "cache"):
        (root / name).mkdir()
    shutil.copytree(Path(__file__).resolve().parents[1] / ".config/yuke/plugins/loop", profile / "loop")
    probe = profile / "probe"
    probe.mkdir()
    (probe / "plugin.json").write_text(json.dumps({"name": "loop-probe", "extensions": {"sh.yuke": {"entry": "./index.js", "uses": ["tui"]}}}))
    (probe / "index.js").write_text('''
import { client } from "yuke";
import { currentPane } from "yuke:session";
export default function(ctx) {
  ctx.on("notify.posted", note => ctx.print("LOOP_NOTICE", note.message));
  const tui = ctx.get("tui");
  if (!tui) return;
  ctx.once("ui.started", () => ctx.print("LOOP_BOOT"));
  tui.command.add("loop-cancel", { desc: "Cancel the fixture run", slash: true, run() {
    const id = currentPane()?.session.sessionId;
    if (id) void client.sessionCancelRun(id).then(() => ctx.print("LOOP_CANCELED"));
  } });
}
''')
    (profile / "config.json").write_text(json.dumps({"plugins": ["./loop", "./probe"]}))
    requests = []
    errors = []
    ticks = []
    release = threading.Event()

    class Provider(http.server.BaseHTTPRequestHandler):
        def log_message(self, *unused):
            pass

        def do_POST(self):
            holding = False
            try:
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                requests.append(body)
                holding = "[yuke-loop " in json.dumps(body["messages"])
                if holding:
                    ticks.append(body)
                if holding and len(ticks) == 3:
                    failed = json.dumps({"error": {"message": "fixture rejected this turn"}}).encode()
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(failed)))
                    self.end_headers()
                    self.wfile.write(failed)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                first = {"choices": [{"delta": {"content": "LOOP_REPLY"}, "finish_reason": None}]}
                self.wfile.write(("data: " + json.dumps(first) + "\n\n").encode())
                self.wfile.flush()
                if holding and len(ticks) == 1:
                    release.wait(20)
                last = {"choices": [{"delta": {}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 100, "completion_tokens": 1}}
                self.wfile.write(("data: " + json.dumps(last) + "\n\ndata: [DONE]\n\n").encode())
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                if not holding:
                    errors.append("Unexpected provider disconnect")
            except Exception as error:
                errors.append(str(error))

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Provider)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    (profile / "providers.json").write_text(json.dumps({"providers": [{"id": "loop-test", "base_url": f"http://127.0.0.1:{server.server_port}/v1", "api_key": "fixture-only", "endpoints": [{"protocol": "openai_chat", "credential_header": "authorization_bearer"}], "models": [{"id": "model", "upstream_id": "model", "flags": {"supports_tools": True}, "limits": {"context_window": 100000, "max_output_tokens": 4096}}]}]}))
    (profile / "providers.json").chmod(0o600)
    env = {"PATH": os.environ["PATH"], "HOME": str(root / "home"), "TERM": "xterm-256color", "YUKE_APPNAME": "yuke"}
    for name in ("config", "data", "state", "cache"):
        env["XDG_" + name.upper() + "_HOME"] = str(root / name)
    socket = "yuke-loop-" + uuid.uuid4().hex[:12]
    captures = []

    def mux(*args):
        return subprocess.check_output(["tmux", "-L", socket, *args], text=True)

    def screen():
        return mux("capture-pane", "-p", "-t", "loop")

    def logs():
        return "\n".join(p.read_text(errors="replace") for p in (root / "state").rglob("*.log"))

    def wait(condition, label):
        end = time.monotonic() + 12
        while time.monotonic() < end:
            if condition():
                captures.append(label + "\n" + screen())
                return
            time.sleep(0.05)
        raise AssertionError(label + "\n" + screen() + "\n" + logs())

    def send(text):
        subprocess.run(["tmux", "-L", socket, "load-buffer", "-b", "input", "-"], input=text, text=True, check=True)
        mux("paste-buffer", "-d", "-p", "-b", "input", "-t", "loop")
        mux("send-keys", "-t", "loop", "Enter")

    def idle():
        with sqlite3.connect((root / "data/yuke/yuke.db").as_uri() + "?mode=ro", uri=True) as db:
            return db.execute("SELECT open_run_id FROM sessions WHERE id=?", (bytes.fromhex(sid),)).fetchone()[0] is None

    try:
        seed = subprocess.run([str(binary), "-p", "LOOP_SEED", "--json", "--model", "loop-test/model"], env=env, cwd=root / "work", capture_output=True, text=True, timeout=30)
        assert seed.returncode == 0, seed.stderr
        sid = json.loads(seed.stdout)["session_id"]
        assert any(tool.get("function", {}).get("name") == "loop" for tool in requests[0].get("tools", [])), "headless request omitted loop tool"
        command = shlex.join(["env", "-i", *(f"{k}={v}" for k, v in env.items()), str(binary), "resume", sid])
        mux("new-session", "-d", "-x", "120", "-y", "36", "-s", "loop", "-n", "Agent Tests loop", "-c", str(root / "work"), command)
        wait(lambda: "LOOP_BOOT" in logs(), "saved source loaded")
        send("/loop 1s Finish the fixture, then stop.")
        wait(lambda: len(ticks) == 1, "native scheduled input delivered")
        send("/loop-cancel")
        wait(lambda: "LOOP_CANCELED" in logs() and idle(), "native run canceled")
        release.set()
        send("/loop list")
        wait(lambda: ": paused," in logs(), "canceled run pauses its loop")
        time.sleep(1.4)
        assert len(ticks) == 1, "paused loop delivered another tick"
        send("/loop stop")
        wait(lambda: "Stopped 1 loop(s)" in logs(), "owned schedule stopped")
        send("/loop 1s Test native reload cleanup.")
        wait(lambda: len(ticks) >= 2 and idle(), "explicit rearm delivers")
        count = len(ticks)
        send("/reload")
        wait(lambda: logs().count("LOOP_BOOT") == 2, "native profile reloaded")
        send("/loop list")
        wait(lambda: "No loops armed" in logs(), "reload restores no schedules")
        time.sleep(1.4)
        assert len(ticks) == count, "reload left a live timer"
        paused = logs().count(": paused,")
        send("/loop 1s Stop after a failed fixture turn.")
        wait(lambda: len(ticks) == 3 and idle(), "failed native turn finished")
        send("/loop list")
        wait(lambda: logs().count(": paused,") > paused, "failed turn pauses its loop")
        time.sleep(1.4)
        assert len(ticks) == 3, "failed turn delivered another tick"
        send("/loop stop")
        assert not errors, errors
        print(json.dumps({"headless_tool": True, "native_tick": True, "cancel_pauses": True, "failure_pauses": True, "stop": True, "reload_disposes": True, "ticks": len(ticks), "artifacts": str(root)}, indent=2))
    finally:
        release.set()
        (root / "captures.txt").write_text("\n".join(captures))
        (root / "requests.json").write_text(json.dumps(requests, indent=2))
        subprocess.run(["tmux", "-L", socket, "kill-server"], capture_output=True)
        server.shutdown()
        server.server_close()
        print("Loop artifacts:", root)


if __name__ == "__main__":
    main()
