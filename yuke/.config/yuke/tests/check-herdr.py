#!/usr/bin/env python3
"""Check Herdr's Yuke-to-agent state mapping in an isolated profile."""
import json
import os
import pathlib
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import uuid

TMUX = shutil.which("tmux")
YUKE = shutil.which("yuke")
assert TMUX, "tmux is required"
assert YUKE, "yuke is required"
plugin = pathlib.Path(__file__).resolve().parents[1] / "plugins" / "herdr.js"

profile_source = r'''
import { plugins } from "yuke";
import { herdr, herdrAgentState, herdrPromptSummary } from PLUGIN;
plugins.use(herdr());
const assistant = (error) => ({ id: 2, type: "assistant", ...(error ? { error } : {}) });
const failed = { messages: [
  { id: 1, type: "user" },
  assistant({ type: "timeout", message: "provider stream timed out" }),
], active: null };
const recovered = { messages: [...failed.messages, { id: 3, type: "user" }, assistant()], active: null };
const checks = [
  ["empty chat", herdrAgentState(0, false, null), "idle"],
  ["active run", herdrAgentState(0, true, failed), "working"],
  ["pending interaction", herdrAgentState(1, true, failed), "blocked"],
  ["provider timeout", herdrAgentState(0, false, failed), "blocked"],
  ["successful retry", herdrAgentState(0, false, recovered), "idle"],
];
for (const [name, actual, expected] of checks) {
  if (actual !== expected) throw new Error(`${name}: expected ${expected}, got ${actual}`);
}
const prompt = herdrPromptSummary([
  { type: "text", text: "  Improve\n\n the   agent sidebar " },
  { type: "image" },
  { type: "text", text: "with session context.  " },
]);
if (prompt !== "Improve the agent sidebar with session context.") throw new Error(`normalized prompt: ${prompt}`);
const longPrompt = herdrPromptSummary([{ type: "text", text: "one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen" }]);
if (!longPrompt.endsWith("…") || longPrompt.length > 72 || longPrompt.endsWith(" …")) throw new Error(`clipped prompt: ${longPrompt}`);
'''

with tempfile.TemporaryDirectory(prefix="yuke-herdr-") as directory:
    root = pathlib.Path(directory)
    profile = root / "config" / "yuke"
    profile.mkdir(parents=True)
    (profile / "index.js").write_text(profile_source.replace("PLUGIN", json.dumps(str(plugin))))
    socket_path = root / "herdr.sock"
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(socket_path))
    server.listen()
    server.settimeout(0.05)
    requests = []
    stopped = threading.Event()

    def serve():
        while not stopped.is_set():
            try:
                connection, _ = server.accept()
            except socket.timeout:
                continue
            with connection:
                data = b""
                while not data.endswith(b"\n"):
                    chunk = connection.recv(4096)
                    if not chunk:
                        break
                    data += chunk
                if not data:
                    continue
                request = json.loads(data)
                requests.append(request)
                response = {"id": request["id"], "result": {"type": "ok"}}
                connection.sendall((json.dumps(response) + "\n").encode())

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    env = {
        **os.environ,
        "XDG_CONFIG_HOME": str(root / "config"),
        "XDG_DATA_HOME": str(root / "data"),
        "XDG_STATE_HOME": str(root / "state"),
        "XDG_CACHE_HOME": str(root / "cache"),
        "HERDR_ENV": "1",
        "HERDR_PANE_ID": "test-pane",
        "HERDR_SOCKET_PATH": str(socket_path),
        "TERM": "xterm-256color",
    }
    for name in ("AI_AGENT", "CLAUDECODE"):
        env.pop(name, None)
    try:
        result = subprocess.run(
            [YUKE, "check"], env=env, check=False, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        if result.returncode:
            raise AssertionError(f"isolated yuke check failed\n{result.stdout}")
        time.sleep(0.1)
        if requests:
            raise AssertionError("yuke check reported or released its parent Herdr pane")

        tmux_socket = "yuke-herdr-" + uuid.uuid4().hex[:10]
        subprocess.run(
            [TMUX, "-L", tmux_socket, "new-session", "-d", "-x", "80", "-y", "24", "-s", "test", YUKE],
            env=env, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if any(request["method"] == "pane.report_agent" and request["params"]["state"] == "idle" for request in requests):
                break
            time.sleep(0.05)
        else:
            raise AssertionError(f"interactive yuke did not report idle to Herdr: {requests}")
    finally:
        if "tmux_socket" in locals():
            subprocess.run([TMUX, "-L", tmux_socket, "kill-server"], check=False,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            time.sleep(0.1)
        stopped.set()
        thread.join(timeout=1)
        server.close()

print("Herdr state check passed")
