#!/usr/bin/env python3
"""Verify timing logs without model calls, desktop input, or waiting 30 real seconds."""
import json
import pathlib
import shlex
import shutil
import subprocess
import tempfile
import time
import uuid

TMUX = shutil.which("tmux")
YUKE = shutil.which("yuke")
assert TMUX and YUKE, "tmux and yuke are required"
plugin = pathlib.Path(__file__).resolve().parents[1] / "plugins" / "step-trace.js"
socket = "yuke-step-trace-" + uuid.uuid4().hex[:10]
captures = []
PROFILE = r'''
import { client, events, plugins } from "yuke";
import { currentPane } from "yuke:session";
import { stepTrace } from PLUGIN;
plugins.use({ name: "trace-probe", apply(ctx) {
  const hooks = {};
  ctx.advise(ctx, "hook", "before", (point, fn) => { hooks[point] = fn; });
  let offset = 0;
  const realNow = Date.now;
  Date.now = () => realNow() + offset;
  ctx.own(() => { Date.now = realNow; });
  const parts = {
    a: { type: "tool", id: 1, call_id: "a", name: "exec", arguments: '{"command":"sed -- SECRET_VALUE"}', state: { type: "pending" } },
    b: { type: "tool", id: 1, call_id: "b", name: "exec", arguments: '{"command":"sed -- OTHER_SECRET"}', state: { type: "pending" } },
  };
  ctx.advise(client, "sessionParts", "around", (_next, session, message) => message === 42 ? [parts[session]] : [{ type: "text", id: 0, text: "next message" }]);
  ctx.advise(client, "sessionPart", "around", (_next, session, message) => ({ part: message === 42 ? parts[session] : { type: "text", id: 0, text: "next message" }, cursor: null, tail: false }));
  stepTrace.apply(ctx);
  // Advice runs first-registration outermost. Keep the real logger outside the stub.
  ctx.advise(client, "sessionCancelRun", "around", (_next, session) => session === "b" ? Promise.reject(new Error("probe")) : Promise.resolve({}));
  const drain = (session, facts = ["tool.state_changed"]) => events.emit("engine.drained", { type: "session", session, kind: "active", id: 42, part: 1, facts });
  const before = session => hooks["tool.before"]({ name: "exec", arguments: parts[session].arguments,
    context: { session_id: session, parent_id: null, depth: 0, max_agent_depth: 1, agent_name: "", workspace: "/probe" } });
  const phase = () => events.emit("activity.changed", "a", { state: { type: "waiting", run_id: 1, started_at_ms: Date.now() }, queued: 1, context_tokens: 0 });
  ctx.inject(["tui"], c => {
    const input = currentPane().composer.input;
    drain("a", ["message.part_added"]);
    drain("b", ["message.part_added"]);
    phase(); phase();
    input.setText("TRACE READY");
    c.tui.command.add("advance", { run() { offset += 31000; input.setText("TRACE ADVANCED"); }});
    c.tui.command.add("settle", { run() {
      before("a");
      parts.a.state = { type: "running", started_at_ms: Date.now() - 100 };
      drain("a");
      hooks["tool.after"]({ name: "exec", arguments: parts.a.arguments, output: "SECRET_OUTPUT", is_error: false });
      parts.a.state = { type: "completed", duration_ms: 123, output: "SECRET_OUTPUT" };
      // Completion and the next message coalesce. The drain no longer names tool 42:1.
      events.emit("engine.drained", { type: "session", session: "a", kind: "active", id: 43, part: 0, facts: ["tool.state_changed", "message.committed", "message.started"] });
      parts.b.state = { type: "canceled" };
      drain("b");
      client.sessionCancelRun("a").then(() => {
        client.sessionCancelRun("b").catch(() => { input.setText("TRACE SETTLED"); });
      });
    }});
    c.tui.command.add("done", { run() {
      drain("a", ["run.done"]); drain("b", ["run.done"]);
      input.setText("TRACE DONE");
    }});
    c.tui.keymap.add({ "alt+a": "trace-probe:advance", "alt+s": "trace-probe:settle", "alt+d": "trace-probe:done" });
  });
}});
'''


def tmux(*args, check=True):
    return subprocess.run([TMUX, "-L", socket, *args], check=check, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def wait_screen(label, text):
    deadline = time.monotonic() + 7
    while time.monotonic() < deadline:
        screen = tmux("capture-pane", "-t", "test", "-p").stdout
        if text in screen:
            captures.append(f"=== {label} ===\n{screen}")
            return
        time.sleep(0.05)
    raise AssertionError(f"missing {text}\n{screen}")


try:
    with tempfile.TemporaryDirectory(prefix="yuke-step-trace-") as directory:
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
        tmux("new-session", "-d", "-x", "100", "-y", "24", "-s", "test", str(run))
        wait_screen("two pending calls with identical numeric IDs", "TRACE READY")
        tmux("send-keys", "-t", "test", "M-a")
        wait_screen("advance diagnostic clock", "TRACE ADVANCED")
        time.sleep(1.2)
        tmux("send-keys", "-t", "test", "M-s")
        wait_screen("execution, cancellation, and hook boundaries", "TRACE SETTLED")
        tmux("send-keys", "-t", "test", "M-d")
        wait_screen("run boundaries", "TRACE DONE")
        time.sleep(0.2)
        raw = "\n".join(p.read_text() for p in (root / "state").rglob("*.log"))
        records = [json.loads(line.split("STEP_TRACE ", 1)[1]) for line in raw.splitlines() if "STEP_TRACE " in line]
        assert not any(secret in raw for secret in ["SECRET_VALUE", "OTHER_SECRET", "SECRET_OUTPUT"]), raw
        pending = [r for r in records if r["event"] == "tool.pending"]
        assert {r["session"] for r in pending} == {"a", "b"}, records
        assert all(r["execution_elapsed_ms"] is None for r in pending)
        heartbeats = [r for r in records if r["event"] == "tool.still_unsettled"]
        assert {r["session"] for r in heartbeats} == {"a", "b"}, records
        assert all(r["state"] == "pending" and r["execution_elapsed_ms"] is None and r["observed_elapsed_ms"] >= 30000 for r in heartbeats)
        assert any(r["event"] == "clock_or_event_loop_gap" for r in records)
        assert any(r["event"] == "phase.still_active" and r["state"] == "waiting" and r["elapsed_ms"] >= 30000 for r in records)
        running = next(r for r in records if r["event"] == "tool.running")
        assert running["session"] == "a" and running["engine_started_at_ms"] is not None
        settled = {r["session"]: r for r in records if r["event"] == "tool.settled"}
        assert settled["a"]["engine_duration_ms"] == 123
        assert settled["b"]["state"] == "canceled" and settled["b"]["execution_elapsed_ms"] is None
        assert settled["b"]["engine_duration_ms"] is None
        before = next(r for r in records if r["event"] == "tool.before")
        after = next(r for r in records if r["event"] == "tool.after")
        assert before["fingerprint"] == after["fingerprint"] == settled["a"]["fingerprint"]
        assert "session" not in after, "the after hook does not expose a session ID"
        assert len([r for r in records if r["event"] == "phase"]) == 1, "identical phase events should not flood logs"
        assert any(r["event"] == "cancel.resolved" for r in records)
        assert any(r["event"] == "cancel.rejected" for r in records)
        assert len([r for r in records if r["event"] == "run.finished"]) == 2
        time.sleep(1.2)
        later = "\n".join(p.read_text() for p in (root / "state").rglob("*.log"))
        assert later == raw, "settled runs must stop diagnostic pulses"
        captures.append("=== structured diagnostic records ===\n" + "\n".join(json.dumps(r) for r in records))
finally:
    tmux("kill-server", check=False)
    with tempfile.NamedTemporaryFile(prefix="yuke-step-trace-", suffix=".txt", mode="w", delete=False) as artifact:
        artifact.write("\n".join(captures))
        print("Saved step trace artifact:", artifact.name)

print("Step trace tmux check passed")
