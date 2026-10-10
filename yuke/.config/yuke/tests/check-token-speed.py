#!/usr/bin/env python3
"""Exercise token speed in a detached TUI, without credentials or provider calls."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import uuid

TMUX = shutil.which("tmux")
YUKE = shutil.which("yuke")
assert TMUX and YUKE, "tmux and yuke are required"
PLUGIN = Path(__file__).resolve().parents[1] / "plugins" / "token-speed.js"
SOCKET = "yuke-token-speed-" + uuid.uuid4().hex[:10]
CAPTURES = []


def tmux(*args, check=True):
    return subprocess.run([TMUX, "-L", SOCKET, *args], check=check, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def expect(label, text, absent=()):
    deadline = time.monotonic() + 8
    screen = ""
    while time.monotonic() < deadline:
        screen = tmux("capture-pane", "-t", "test", "-p").stdout
        if text in screen and all(word not in screen for word in absent):
            CAPTURES.append(f"=== {label} ===\n{screen}")
            return
        time.sleep(0.05)
    CAPTURES.append(f"=== FAILED {label} ===\n{screen}")
    raise AssertionError(f"{label}: expected {text!r}, absent {absent}\n{screen}")


def command(name):
    tmux("send-keys", "-t", "test", "-l", "/" + name)
    tmux("send-keys", "-t", "test", "Enter")
    time.sleep(0.1)


try:
    with tempfile.TemporaryDirectory(prefix="yuke-token-speed-") as directory:
        root = Path(directory)
        profile = root / "config" / "yuke"
        profile.mkdir(parents=True)
        (profile / "index.js").write_text('''
import { client, events, plugins } from "yuke";
import { currentPane } from "yuke:session";
import { tokenSpeed } from PLUGIN;
let now = 1000, active = null, messages = [], parts = [], history = [], fail = false;
let handle;
plugins.use({ name: "speed-probe", apply(ctx) {
  ctx.advise(Date, "now", "filterReturn", () => now);
  ctx.advise(client, "sessionOutline", "around", () => ({ messages, active }));
  ctx.advise(client, "sessionParts", "around", () => parts);
  ctx.advise(client, "request", "around", (_next, method, params) => {
    if (method !== "session.history") throw new Error("unexpected provider request: " + method);
    if (params.limit !== 1) throw new Error("unbounded history query");
    return fail ? Promise.reject(new Error("fixture failure")) : Promise.resolve({ messages: history });
  });
  ctx.inject(["tui"], c => {
    const pane = currentPane();
    if (!pane) throw new Error("no pane");
    pane.session.sessionId = "speed-session";
    const emit = (...facts) => events.emit("engine.drained", {
      type: "session", session: "speed-session", kind: active ? "active" : "quiet", facts
    });
    const add = (name, run) => c.tui.command.add(name, { slash: true, desc: name, run });
    const start = (id) => {
      active = { id, type: "assistant" }; parts = [];
      emit("message.started");
    };
    const commit = (tokens) => {
      const id = active.id;
      history = [{ type: "assistant", id, tokens,
        content: parts, time: { created_at_ms: 1000, completed_at_ms: now } }];
      messages.push({ type: "assistant", id }); active = null;
      emit("message.committed", "run.done");
    };
    add("speed-start", () => start(1));
    add("speed-text", () => {
      now = 3000; parts = [{ type: "text", id: 1, text: "a".repeat(400) }];
      emit("message.part_delta");
    });
    add("speed-tools", () => {
      now = 4000; parts.push({ type: "tool", id: 2, arguments: "", state: { type: "running", started_at_ms: now } });
      emit("tool.state_changed");
    });
    add("speed-tool-output", () => { now = 9000; emit("tool.output_delta"); });
    add("speed-commit", () => commit({ output: 300, reasoning: 100 }));
    add("speed-next", () => { now = 10000; start(2); });
    add("speed-next-commit", () => { now = 12000; commit({ output: 160, reasoning: 40 }); });
    add("speed-other-pane", () => { pane.session.sessionId = "other-session"; c.tui.root.invalidatePaint(); });
    add("speed-first-pane", () => { pane.session.sessionId = "speed-session"; c.tui.root.invalidatePaint(); });
    add("speed-no-usage", () => { now = 13000; start(3); now = 14000; commit(undefined); });
    add("speed-failed-history", () => { now = 15000; start(4); fail = true; now = 16000; commit({ output: 99 }); });
    add("speed-discard", () => { now = 17000; start(5); active = null; emit("message.discarded", "run.done"); });
    add("speed-unload", () => { void handle.dispose(); });
  });
}});
handle = plugins.use(tokenSpeed);
'''.replace("PLUGIN", json.dumps(str(PLUGIN))))
        run = root / "run.sh"
        run.write_text("#!/bin/sh\n" + "\n".join(
            f"export XDG_{name}_HOME={json.dumps(str(root / name.lower()))}"
            for name in ("CONFIG", "DATA", "STATE", "CACHE")) +
            '\nunset HERDR_ENV HERDR_PANE_ID HERDR_SOCKET_PATH YUKE_APPNAME AI_AGENT CLAUDECODE\n'
            'export TERM=xterm-256color\n' + f'exec {json.dumps(YUKE)}\n')
        run.chmod(0o700)
        tmux("new-session", "-d", "-x", "120", "-y", "28", "-s", "test", str(run))
        expect("initial unknown speed", "— tok/s")
        command("speed-start")
        expect("waiting for output", "— tok/s")
        command("speed-text")
        expect("live estimate", "~50.0 tok/s")
        command("speed-tools")
        expect("stop model timer before tools", "~33.3 tok/s")
        command("speed-tool-output")
        expect("tool output excluded", "~33.3 tok/s")
        command("speed-commit")
        expect("provider usage, reasoning not double counted, tool time excluded", "100.0 tok/s", absent=("~100.0",))
        command("speed-next")
        expect("next round resets live measurement", "— tok/s", absent=("100.0 tok/s",))
        command("speed-next-commit")
        expect("next provider response", "80.0 tok/s", absent=("~80.0",))
        command("speed-other-pane")
        expect("pane isolation", "— tok/s", absent=("80.0 tok/s",))
        command("speed-first-pane")
        expect("original pane retains speed", "80.0 tok/s")
        command("speed-no-usage")
        expect("missing usage is not zero or stale speed", "— tok/s", absent=("80.0 tok/s",))
        command("speed-failed-history")
        expect("history failure is safe", "— tok/s")
        command("speed-discard")
        expect("discarded draft is safe", "— tok/s")
        command("speed-unload")
        expect("plugin cleanup", "0 context", absent=("tok/s",))
finally:
    tmux("kill-server", check=False)
    with tempfile.NamedTemporaryFile(prefix="yuke-token-speed-", suffix=".txt", mode="w", delete=False) as artifact:
        artifact.write("\n".join(CAPTURES))
        print("Saved token speed transcript:", artifact.name)

print("Token speed tmux checks passed")
