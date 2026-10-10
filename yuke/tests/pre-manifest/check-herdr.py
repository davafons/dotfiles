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
import { events, plugins } from "yuke";
import { herdr, herdrAgentState, herdrPromptSummary } from PLUGIN;
plugins.use(herdr());
import { currentPane } from "yuke:session";
plugins.use({ name: "herdr-session-probe", apply(ctx) {
  ctx.inject(["tui"], c => {
    let index = 0;
    c.tui.keymap.add({ "ctrl+t": () => {
      currentPane().session.sessionId = ["1".repeat(32), "2".repeat(32), null, "2".repeat(32)][index++];
      events.emit("session.current.changed");
      c.tui.root.invalidatePaint();
    } }, "chat && !overlay");
    c.tui.status.add({ side: "left", render: () => "HERDR SESSION PROBE" });
  });
}});
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
    captures = []
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
        for expected in ("1" * 32, "2" * 32, ""):
            subprocess.run([TMUX, "-L", tmux_socket, "send-keys", "-t", "test", "C-t"], check=True)
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                reports = [r for r in requests if r["method"] == "pane.report_metadata"]
                if reports and reports[-1]["params"]["tokens"].get("yuke_session_id") == expected:
                    break
                time.sleep(0.05)
            else:
                raise AssertionError(f"session mapping did not change to {expected!r}: {requests}")
            assert reports[-1]["params"]["tokens"]["summary"] == "", "mapping depended on a changed prompt summary"
            states = [r for r in requests if r["method"] == "pane.report_agent"]
            if expected:
                assert states[-1]["params"].get("agent_session_id") == expected, "state report kept a stale session"
                assert states[-1]["params"].get("resume_argv") == ["yuke", "resume", expected], "resume command did not follow the current session"
            else:
                assert "resume_argv" not in states[-1]["params"], "draft reported an old resume command"
                assert any(r["method"] == "pane.release_agent" for r in requests), "draft did not clear the previous resume command"
            captures.append(f"=== reported session {expected!r} ===\n" + subprocess.check_output(
                [TMUX, "-L", tmux_socket, "capture-pane", "-t", "test", "-p"], text=True))
        # Exit while a session is held, so disposal must clear its mapping.
        subprocess.run([TMUX, "-L", tmux_socket, "send-keys", "-t", "test", "C-t"], check=True)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            reports = [r for r in requests if r["method"] == "pane.report_metadata"]
            if reports[-1]["params"]["tokens"].get("yuke_session_id") == "2" * 32:
                break
            time.sleep(0.05)
        else:
            raise AssertionError("could not restore a session before exit")
        releases_before_exit = sum(r["method"] == "pane.release_agent" for r in requests)
        subprocess.run([TMUX, "-L", tmux_socket, "send-keys", "-t", "test", "C-q"], check=True)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if sum(r["method"] == "pane.release_agent" for r in requests) > releases_before_exit:
                break
            time.sleep(0.05)
        else:
            raise AssertionError(f"exit did not release the Herdr agent: {requests}")
        metadata = [r for r in requests if r["method"] == "pane.report_metadata"]
        assert metadata[-1]["params"]["tokens"] == {"summary": "", "yuke_session_id": ""}, "exit left a stale session mapping"

    finally:
        if "tmux_socket" in locals():
            subprocess.run([TMUX, "-L", tmux_socket, "kill-server"], check=False,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            time.sleep(0.1)
        stopped.set()
        thread.join(timeout=1)
        server.close()
        with tempfile.NamedTemporaryFile(prefix="yuke-herdr-", suffix=".txt", mode="w", delete=False) as artifact:
            artifact.write("\n".join(captures) + "\n=== socket requests ===\n" + json.dumps(requests, indent=2))
            print("Saved Herdr report transcript:", artifact.name)

print("Herdr state check passed")
