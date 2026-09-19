#!/usr/bin/env python3
"""Check the split session finder and its keys in an isolated Yuke TUI."""
import fcntl
import json
import pathlib
import shutil
import subprocess
import tempfile
import time
import uuid

TMUX = shutil.which("tmux")
YUKE = shutil.which("yuke")
assert TMUX, "tmux is required"
assert YUKE, "yuke is required"
plugin = pathlib.Path(__file__).resolve().parents[1] / "plugins" / "sessions-reworked.js"
session = "yuke-sessions-" + uuid.uuid4().hex[:10]
transcript = []


def tmux(*args, check=True):
    return subprocess.run(
        [TMUX, *args], check=check, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )


def capture(target, label):
    screen = tmux("capture-pane", "-t", target, "-p", "-S", "-40").stdout
    transcript.append(f"=== {label} ===\n{screen}")
    return screen


def wait_screen(target, label, accept, timeout=5):
    deadline = time.monotonic() + timeout
    screen = ""
    while time.monotonic() < deadline:
        screen = capture(target, label)
        if accept(screen):
            return screen
        transcript.pop()
        time.sleep(0.05)
    raise AssertionError(f"timed out at {label}\n{screen}")


profile_source = r'''
import { client, plugins } from "yuke";
import { sessionsReworked } from PLUGIN;
const now = Date.now();
const activity = (state, context = 0) => ({ state, queued: 0, context_tokens: context });
const item = (session, state, context = 0) => ({ session: {
  reasoning: "", config_rev: 1, max_rounds: 20,
  usage_total: { input: 0, output: 0, reasoning: 0, cache_read: 0, cache_write: 0 },
  cost: { total: 0, without_cache: 0, unpriced: 0 }, created_at_ms: now, updated_at_ms: now,
  origin: { type: "root" }, ...session,
}, activity: activity(state, context) });
const newest = item({
  id: "session-newest", root: WORKSPACE, model: "openai-codex/gpt-6-luna", reasoning: "high",
  title: "yuke", message_count: 12,
  usage_total: { input: 12340, output: 2345, reasoning: 345, cache_read: 8000, cache_write: 200 },
  cost: { total: 0.123, without_cache: 0.2, unpriced: 0 },
  created_at_ms: now - 2 * 60 * 60 * 1000, updated_at_ms: now - 5 * 60 * 1000,
}, { type: "waiting", run_id: 2, started_at_ms: now - 3000 }, 45678);
const older = item({
  id: "session-older", root: "/workspace/older", model: "anthropic/claude", title: "Older design session", name: "qqqqqq", message_count: 3,
  created_at_ms: now - 7 * 24 * 60 * 60 * 1000, updated_at_ms: now - 2 * 60 * 60 * 1000,
  origin: { type: "fork", source_id: "source-session" },
}, { type: "idle" });
const foreign = item({
  id: "session-active-elsewhere", root: WORKSPACE, model: "openai-codex/gpt-6-luna", title: "Active in another Yuke", message_count: 6,
  created_at_ms: now - 60 * 60 * 1000, updated_at_ms: now - 10 * 60 * 1000,
}, { type: "idle" });
client.sessionList = async (params = {}) => params.cursor
  ? { revision: 1, items: [newest, foreign], total: 3 }
  : { revision: 1, items: [older], next_cursor: "page-2", total: 3 };
const histories = {
  "session-newest": [
    { type: "user", id: 1, input_id: 1, time: { created_at_ms: now - 6000 }, content: [{ type: "text", text: "Please inspect the newest project." }] },
    { type: "assistant", id: 2, run_id: 1, config_rev: 1, time: { created_at_ms: now - 5000, completed_at_ms: now - 4000 }, finish: "stop", content: [
      { type: "tool", id: 0, name: "read", arguments: '{"path":"src/main.zig"}', state: { type: "completed", output: "const ready = true;", duration_ms: 3 } },
      { type: "text", id: 1, text: Array.from({ length: 120 }, (_, i) => "Preview detail " + (i + 1) + ".").join("\n") + "\nThe newest project is ready for review." },
    ] },
  ],
  "session-older": [
    { type: "user", id: 3, input_id: 2, time: { created_at_ms: now - 3000 }, content: [{ type: "text", text: "Compare the older design." }] },
    { type: "assistant", id: 4, run_id: 2, config_rev: 1, time: { created_at_ms: now - 2000, completed_at_ms: now - 1000 }, finish: "stop", content: [{ type: "text", id: 0, text: "The older design uses the first layout." }] },
  ],
};
client.request = async (method, params) => {
  if (method !== "session.history") throw new Error("unexpected method " + method);
  const messages = histories[params.session_id] || [];
  if (params.session_id === newest.session.id && params.before_message_id === 0) {
    return { session_id: params.session_id, messages: messages.slice(1), configs: [], has_more: true };
  }
  return { session_id: params.session_id, messages: params.session_id === newest.session.id ? messages.slice(0, 1) : messages, configs: [], has_more: false };
};
client.sessionOpen = () => true;
client.sessionClose = () => {};
client.sessionActivity = (id) => id === newest.session.id ? newest.activity : older.activity;
client.sessionOutline = () => ({ messages: [], active: null });
client.sessionCheckContext = async () => newest;
plugins.use(sessionsReworked);
plugins.use({ name: "session-browser-test", apply(ctx) {
  ctx.inject(["tui"], c => {
    c.tui.status.add({ side: "left", render: () => "SESSION TEST READY" });
  });
}});
'''

lock_file = None
try:
    with tempfile.TemporaryDirectory(prefix="yuke-sessions-") as directory:
        root = pathlib.Path(directory)
        profile = root / "config" / "yuke"
        profile.mkdir(parents=True)
        workspace = root / "workspace"
        workspace.mkdir()
        workspace = workspace.resolve()
        owners = root / "data" / "yuke" / "yuke.db.owners"
        owners.mkdir(parents=True)
        lock_file = (owners / "session-active-elsewhere.lock").open("a+b")
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        source = profile_source.replace("PLUGIN", json.dumps(str(plugin))).replace("WORKSPACE", json.dumps(str(workspace)))
        (profile / "index.js").write_text(source)
        run = root / "run.sh"
        run.write_text(
            "#!/bin/sh\n"
            f"export XDG_CONFIG_HOME={json.dumps(str(root / 'config'))}\n"
            f"export XDG_DATA_HOME={json.dumps(str(root / 'data'))}\n"
            f"export XDG_STATE_HOME={json.dumps(str(root / 'state'))}\n"
            f"export XDG_CACHE_HOME={json.dumps(str(root / 'cache'))}\n"
            "export TERM=xterm-256color\n"
            f"cd {json.dumps(str(workspace))}\n"
            f"exec {json.dumps(YUKE)}\n"
        )
        run.chmod(0o700)
        tmux("new-session", "-d", "-x", "140", "-y", "40", "-s", session, str(run))
        target = tmux("list-panes", "-t", session, "-F", "#{pane_id}").stdout.strip()
        wait_screen(target, "initial session", lambda text: "SESSION TEST READY" in text)

        tmux("send-keys", "-t", target, "C-f")
        screen = wait_screen(target, "current workspace finder", lambda text: "Sessions · current · workspace · 2" in text and "◆ WORKING  Please inspect the newest project." in text)
        assert "Older design session" not in screen, "the current workspace scope included another workspace"
        assert "Active in another Yuke" in screen and "open elsewhere" in screen, "the finder did not label a session owned by another Yuke process"
        assert "tab all" in screen and "ctrl+n/p sessions" in screen and "ctrl+d/u preview" in screen, "the picker footer did not explain navigation"
        tmux("send-keys", "-t", target, "Tab")
        screen = wait_screen(target, "all workspaces", lambda text: "Sessions · all workspaces · 3" in text and "Older design session" in text)
        assert "tab current" in screen, "the all-workspaces scope did not offer the current workspace"
        assert "closed" in screen, "the finder did not label resumable closed sessions"
        assert "5m ago" in screen, "the list did not show relative update time"
        assert "12 messages" in screen, "the preview did not show the message count"
        assert str(workspace)[:60] in screen, "the preview did not show the workspace"
        assert "Active in another Yuke" in screen and "open elsewhere" in screen, "the all-workspaces finder did not expose ownership state"
        assert "ready for review." in screen, "the preview did not start at the newest response"
        assert screen.count("Please inspect the newest project.") == 1, "the preview started at the oldest edge instead of the bottom"
        tmux("send-keys", "-t", target, "C-u")
        screen = wait_screen(target, "older preview page", lambda text: "Please inspect the newest project." in text)
        assert "src/main.zig" in screen and "[tool:" not in screen, "the preview did not use the chat tool renderer"
        tmux("send-keys", "-t", target, "C-d")
        wait_screen(target, "newest preview page", lambda text: "ready for review." in text)

        tmux("send-keys", "-t", target, "C-n")
        wait_screen(target, "foreign session selection", lambda text: "Active in another Yuke" in text and "open elsewhere" in text)
        tmux("send-keys", "-t", target, "Enter")
        wait_screen(target, "foreign session blocked", lambda text: "Sessions · all workspaces · 3" in text and "open elsewhere" in text)
        tmux("send-keys", "-t", target, "C-n")
        screen = wait_screen(target, "Ctrl+N selection", lambda text: "Compare the older design." in text)
        assert "The older design uses the first layout." in screen, "Ctrl+N did not update the history preview"

        tmux("send-keys", "-t", target, "C-p")
        wait_screen(target, "Ctrl+P foreign selection", lambda text: "Active in another Yuke" in text and "open elsewhere" in text)
        tmux("send-keys", "-t", target, "C-p")
        wait_screen(target, "Ctrl+P newest selection", lambda text: "ready for review." in text)

        tmux("send-keys", "-t", target, "-l", "qqqqqq")
        screen = wait_screen(target, "fuzzy filter", lambda text: "Sessions · all workspaces · 1/3" in text and "Compare the older design." in text)
        assert "Please inspect the newest project." not in screen, "the fuzzy filter kept an unmatched session"

        tmux("send-keys", "-t", target, "Escape")
        wait_screen(target, "closed finder", lambda text: "Sessions ·" not in text)
        tmux("send-keys", "-t", target, "-l", "/resume")
        screen = wait_screen(target, "resume slash menu", lambda text: "alias for /sessions" in text)
        assert "/resume" in screen, "/resume was not listed"
        tmux("send-keys", "-t", target, "Enter")
        wait_screen(target, "resume alias", lambda text: "Sessions · current · workspace · 2" in text and "◆ WORKING  Please inspect the newest project." in text)
        tmux("send-keys", "-t", target, "Escape")
        wait_screen(target, "closed resume finder", lambda text: "Sessions ·" not in text)
        tmux("send-keys", "-t", target, "-l", "/sessions all")
        tmux("send-keys", "-t", target, "Enter")
        wait_screen(target, "sessions all command", lambda text: "Sessions · all workspaces · 3" in text and "ready for review." in text)
finally:
    tmux("kill-session", "-t", session, check=False)
    if lock_file is not None:
        lock_file.close()
    with tempfile.NamedTemporaryFile(prefix="yuke-sessions-", suffix=".txt", mode="w", delete=False) as artifact:
        artifact.write("\n".join(transcript))
        print("Saved session browser transcript:", artifact.name)

print("Session browser tmux check passed")
