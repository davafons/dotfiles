#!/usr/bin/env python3
"""Verify per-step clocks in detached tmux, with no model requests or desktop input."""
import json
import pathlib
import re
import shlex
import shutil
import subprocess
import tempfile
import time
import uuid

TMUX = shutil.which("tmux")
YUKE = shutil.which("yuke")
assert TMUX and YUKE, "tmux and yuke are required"
plugin = pathlib.Path(__file__).resolve().parents[1] / "plugins" / "step-timers.js"
socket = "yuke-step-timers-" + uuid.uuid4().hex[:10]
transcript = []

PROFILE = r'''
import { plugins, events, client } from "yuke";
import { currentPane } from "yuke:session";
import { stepTimers } from PLUGIN;
const handle = plugins.use(stepTimers);
plugins.use({ name: "timer-probe", apply(ctx) {
  ctx.inject(["tui", "chat"], c => {
    const pane = currentPane();
    if (!pane) throw new Error("no chat pane");
    pane.session.sessionId = "timer-fixture";
    const tx = pane.transcript;
    const started = Date.now() - 2100;
    let parts = [
      { type: "tool", id: 1, call_id: "read", name: "read", arguments: '{"path":"silent-read.txt"}', state: { type: "running", started_at_ms: started } },
      { type: "tool", id: 2, call_id: "edit", name: "edit", arguments: '{"path":"silent-edit.txt"}', state: { type: "running", started_at_ms: started - 1400 } },
      { type: "tool", id: 3, call_id: "other", name: "custom_tool", arguments: '{"path":"other.txt"}', state: { type: "pending" } },
      { type: "reasoning", id: 4, text: "", title: "", signature: "" },
    ];
    tx.partsOf = id => id === 42 ? parts : [];
    tx.partOf = (_id, part) => ({ part: parts.find(p => p.id === part), cursor: null, tail: false });
    tx.setOutline([], { id: 42, type: "assistant" });
    c.tui.root.invalidate();
    const update = () => { tx.setActive(42); c.tui.root.invalidate(); };
    c.tui.command.add("complete", { run() {
      parts = [
        { ...parts[0], state: { type: "completed", duration_ms: 87, output: "Read body preserved" } },
        { ...parts[1], state: { type: "completed", duration_ms: 1287, output: "", diff: [{ path: "silent-edit.txt", hunks: [{ old_start: 1, old_lines: 1, new_start: 1, new_lines: 1, lines: ["-old value", "+new value"] }] }] } },
        { ...parts[2], state: { type: "error", duration_ms: 432, error: "Error body preserved" } },
        { ...parts[3], duration_ms: 2345, title: "Summary", text: "Reasoning body preserved" },
        { type: "tool", id: 6, call_id: "exec", name: "exec", arguments: '{"command":"echo timer"}', state: { type: "completed", duration_ms: 12000, output: "Took 9.9s" } },
      ];
      update();
    }});
    c.tui.command.add("cancel", { run() {
      parts = [
        { ...parts[0], state: { type: "canceled", duration_ms: 5432 } },
        { ...parts[1], state: { type: "canceled" } },
        { ...parts[2], state: { type: "running", started_at_ms: Date.now() - 500 } },
        { ...parts[3], duration_ms: 0 },
      ];
      update();
    }});
    c.tui.command.add("restart", { run() {
      parts = [{ type: "reasoning", id: 5, text: "Streaming body", title: "Live summary", signature: "" }];
      update();
    }});
    // Exercise the drain observer before a thought reaches a rendered viewport.
    c.advise(client, "sessionParts", "around", (_next, session, message) => session === "timer-fixture" && message === 42 ? parts : session === "peer-fixture" ? [{ type: "reasoning", id: 4, text: "", title: "", signature: "", duration_ms: 12000 }] : []);
    c.tui.command.add("peer", { run() {
      events.emit("engine.drained", { type: "session", session: "peer-fixture", kind: "quiet", id: 42, facts: ["message.part_finalized", "run.done"] });
    }});
    c.tui.keymap.add({ "alt+y": "timer-probe:peer" });
    c.tui.command.add("observe", { run() {
      events.emit("engine.drained", { type: "session", session: "timer-fixture", kind: "active", id: 42, facts: ["message.part_added"] });
    }});
    c.tui.command.add("done", { run() {
      events.emit("engine.drained", { type: "session", session: "timer-fixture", kind: "quiet", id: 42, facts: ["run.done"] });
    }});
    c.tui.command.add("source", { run() {
      tx.select({ id: 42, row: 0, col: 0 }, { id: 42, row: tx.rowCount(100) - 1, col: 100 });
      ctx.print("TIMER_SOURCE " + JSON.stringify(tx.selectedText(true)));
      tx.clearSelection();
    }});
    c.on("chat.strip", () => [{ text: " ↳ queued follow-up", group: "UIDim" }]);
    const phase = state => {
      pane.session.sessionId = "timer-fixture";
      events.emit("activity.changed", "timer-fixture", { state, queued: 1, context_tokens: 0 });
    };
    c.tui.command.add("wait", { run() { phase({ type: "waiting", run_id: 10, started_at_ms: Date.now() - 700000 }); }});
    c.tui.command.add("respond", { run() { phase({ type: "streaming", run_id: 10, started_at_ms: Date.now() - 700000 }); }});
    c.tui.command.add("tool", { run() { phase({ type: "running_tool", run_id: 10, message_id: 42, part_id: 5, tool_name: "edit", started_at_ms: Date.now() }); }});
    c.tui.command.add("idle", { run() { phase({ type: "idle" }); }});
    c.tui.keymap.add({ "alt+w": "timer-probe:wait", "alt+p": "timer-probe:respond", "alt+t": "timer-probe:tool", "alt+i": "timer-probe:idle" });
    c.tui.command.add("unload", { run() { handle.dispose(); tx.setActive(42); c.tui.root.invalidate(); }});
    c.tui.keymap.add({ "alt+c": "timer-probe:complete", "alt+x": "timer-probe:cancel", "alt+r": "timer-probe:restart", "alt+b": "timer-probe:observe", "alt+d": "timer-probe:done", "alt+s": "timer-probe:source", "alt+u": "timer-probe:unload" });
  });
}});
'''


def tmux(*args, check=True):
    return subprocess.run([TMUX, "-L", socket, *args], check=check, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def capture(label):
    screen = tmux("capture-pane", "-t", "test", "-p").stdout
    transcript.append(f"=== {label} ===\n{screen}")
    return screen


def wait_screen(label, text, timeout=7):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        screen = capture(label)
        if text in screen:
            return screen
        transcript.pop()
        time.sleep(0.05)
    raise AssertionError(f"{label}: missing {text!r}\n{screen}")


def elapsed(screen, subject, state=""):
    match = re.search(re.escape(subject) + r"[^\n]* · " + re.escape(state) + r"(\d+\.\d+)s", screen)
    assert match, f"missing timer for {subject!r}\n{screen}"
    return float(match[1])


def key(stroke):
    tmux("send-keys", "-t", "test", stroke)


try:
    with tempfile.TemporaryDirectory(prefix="yuke-step-timers-") as directory:
        root = pathlib.Path(directory)
        profile = root / "config" / "yuke"
        profile.mkdir(parents=True)
        (profile / "index.js").write_text(PROFILE.replace("PLUGIN", json.dumps(str(plugin))))
        run = root / "run.sh"
        run.write_text("#!/bin/sh\n" + "\n".join(
            f"export {name}={shlex.quote(str(root / suffix))}" for name, suffix in [
                ("XDG_CONFIG_HOME", "config"), ("XDG_DATA_HOME", "data"),
                ("XDG_STATE_HOME", "state"), ("XDG_CACHE_HOME", "cache")]
        ) + "\nexport YUKE_APPNAME=yuke TERM=xterm-256color\n"
          "unset HERDR_ENV HERDR_PANE_ID HERDR_SOCKET_PATH\n"
          f"exec {shlex.quote(YUKE)}\n")
        run.chmod(0o700)
        tmux("new-session", "-d", "-x", "100", "-y", "32", "-s", "test", str(run))
        first = wait_screen("live steps", "thinking · ")
        time.sleep(0.6)
        second = capture("silent steps still advance")
        for subject, state in [("silent-read.txt", "running "), ("silent-edit.txt", "running "),
                               ("other.txt", "not started "), ("thinking", "")]:
            assert elapsed(second, subject, state) >= elapsed(first, subject, state) + 0.4
        assert elapsed(first, "silent-edit.txt", "running ") > elapsed(first, "silent-read.txt", "running ") + 1
        key("M-y")
        time.sleep(0.4)
        isolated = capture("another session's identical IDs do not reset this timer")
        assert elapsed(isolated, "thinking") >= elapsed(second, "thinking") + 0.3
        tmux("resize-window", "-t", "test", "-x", "38", "-y", "32")
        narrow = wait_screen("narrow terminal reserves timer space", "running ")
        assert len(re.findall(r" · running \d+\.\d+s", narrow)) == 2, narrow
        assert re.search(r"thinking · \d+\.\d+s", narrow), narrow
        tmux("resize-window", "-t", "test", "-x", "100", "-y", "32")
        wait_screen("wide terminal restored", "─" * 100)
        key("M-c")
        done = wait_screen("final durations", "thought Summary · 2.3s")
        assert re.search(r"silent-read.txt\s+· 0.1s", done) and re.search(r"silent-edit.txt\s+· 1.3s", done)
        assert re.search(r"other.txt\s+· error 0.4s", done) and "Error body preserved" in done
        assert "-old value" in done and "+new value" in done
        assert "Took 12.0s" not in done, "duplicate renderer duration footer must go"
        assert "Took 9.9s" in done, "the command's own output must stay"
        time.sleep(0.4)
        assert capture("completed clocks freeze") == done
        key("C-o")
        expanded = wait_screen("expanded sources", "Reasoning body preserved")
        assert "Read body preserved" in expanded
        key("M-s")
        time.sleep(0.2)
        logs = "\n".join(p.read_text() for p in (root / "state").rglob("*.log"))
        source = next(line.split("TIMER_SOURCE ", 1)[1] for line in logs.splitlines() if "TIMER_SOURCE " in line)
        assert "Read body preserved" in source and "new value" in source
        assert "running " not in source and " · 0.1s" not in source, "timer must not change copy source"
        key("M-x")
        canceled = wait_screen("cancellation and zero duration", "thought Summary · 0.0s")
        assert "canceled 5.4s" in canceled and "canceled before start time unavailable" in canceled
        time.sleep(0.3)
        assert "canceled 5.4s" in capture("canceled clock stays final")
        key("M-r")
        live = wait_screen("new reasoning block", "thinking Live summary · ")
        key("M-b")
        time.sleep(0.3)
        key("M-d")
        stopped = wait_screen("run ends without final metadata", "thought Live summary · ")
        time.sleep(0.4)
        assert capture("interrupted thought freezes") == stopped
        key("M-w")
        waiting = wait_screen("model wait without a transcript block", "request → waiting for model · ")
        assert "queued follow-up" in waiting, "phase rows must not hide the input queue"
        assert elapsed(waiting, "waiting for model") < 2, "phase time must not use the 700s whole-run stamp"
        time.sleep(0.4)
        advancing = capture("silent model wait advances")
        assert elapsed(advancing, "waiting for model") >= elapsed(waiting, "waiting for model") + 0.3
        key("M-p")
        responding = wait_screen("phase transition", "request → responding · ")
        assert "✓ request → waiting for model" in responding
        key("M-t")
        time.sleep(0.1)
        key("M-w")
        anchored = wait_screen("next phase is tied to last tool", "after edit → waiting for model · ")
        assert "queued follow-up" in anchored
        key("M-i")
        idle = wait_screen("phase history freezes when run ends", "✓ after edit → waiting for model · ")
        time.sleep(0.3)
        assert capture("idle phase history") == idle
        key("M-u")
        unloaded = wait_screen("unloaded default renderer", "thinking Live summary")
        assert "thinking Live summary · " not in unloaded
        logs = "\n".join(p.read_text() for p in (root / "state").rglob("*.log"))
        assert not re.search(r"\[(error|warn)\]", logs), logs
        tmux("resize-window", "-t", "test", "-x", "38", "-y", "32")
        capture("narrow terminal after unload")
finally:
    tmux("kill-server", check=False)
    with tempfile.NamedTemporaryFile(prefix="yuke-step-timers-", suffix=".txt", mode="w", delete=False) as artifact:
        artifact.write("\n".join(transcript))
        print("Saved step timers transcript:", artifact.name)

print("Step timers tmux check passed")
