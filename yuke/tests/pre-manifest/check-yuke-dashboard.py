#!/usr/bin/env python3
"""Verify the dashboard through real keys in an isolated, detached Yuke TUI."""
import http.server
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import threading
import time
import uuid

TMUX = shutil.which("tmux")
YUKE = os.environ.get("YUKE_TEST_BINARY") or shutil.which("yuke")
assert TMUX and YUKE, "tmux and yuke are required"
PROFILE = Path(__file__).resolve().parents[1]
FULL_PROFILE = os.environ.get("YUKE_DASHBOARD_FULL_PROFILE") == "1"
MINIMAL_PROFILE = os.environ.get("YUKE_DASHBOARD_MINIMAL_PROFILE") == "1"
assert not (FULL_PROFILE and MINIMAL_PROFILE), "select only one profile variant"
SOCKET = "yuke-dashboard-" + uuid.uuid4().hex[:10]
CAPTURES = []
REQUESTS = []
ERRORS = []


def tmux(*args, check=True):
    return subprocess.run([TMUX, "-L", SOCKET, *args], check=check, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def expect(label, *words, absent=()):
    deadline = time.monotonic() + 15
    current = ""
    while time.monotonic() < deadline:
        current = tmux("capture-pane", "-t", "test", "-p").stdout
        if all(word in current for word in words) and all(word not in current for word in absent):
            CAPTURES.append(f"=== {label} ===\n{current}")
            return current
        time.sleep(0.05)
    CAPTURES.append(f"=== FAILED {label} ===\n{current}")
    raise AssertionError(f"{label}: expected {words}, absent {absent}\n{current}\n{ERRORS}")


def keys(*values):
    tmux("send-keys", "-t", "test", *values)


def literal(value):
    tmux("send-keys", "-t", "test", "-l", value)


class Provider(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        try:
            REQUESTS.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            assert self.path == "/v1/chat/completions", self.path
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            for delta, finish in (({"content": "Dashboard test reply."}, None), ({}, "stop")):
                event = {"id": "dashboard-test", "choices": [{"index": 0, "delta": delta, "finish_reason": finish}]}
                self.wfile.write(("data: " + json.dumps(event) + "\n\n").encode())
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        except Exception as error:
            ERRORS.append(repr(error))
            self.send_error(500)


server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Provider)
threading.Thread(target=server.serve_forever, daemon=True).start()
try:
    with tempfile.TemporaryDirectory(prefix="yuke-dashboard-") as directory:
        root = Path(directory).resolve()
        workspace = root / "dashboard-workspace"
        workspace.mkdir()
        (workspace / "dashboard-fixture.txt").write_text("dashboard search fixture\n")
        profile = root / "config/yuke"
        (profile / "plugins").mkdir(parents=True)
        for helper in (PROFILE / "plugins").glob("*.py"):
            (profile / "plugins" / helper.name).symlink_to(helper)
        source = (
            'import { plugins, defineConfig } from "yuke";\n'
            'import { composerVim } from "yuke:plugins";\n'
            'import { currentPane } from "yuke:session";\n'
            'import { ChatView } from "yuke:chat";\n'
            'import { Text } from "yuke:ui";\n'
            'defineConfig({ mouse: { copyOnSelect: false } });\n'
        )
        imports = (("yukeDashboard", "yuke-dashboard"),) if MINIMAL_PROFILE else (
            ("yukeDashboard", "yuke-dashboard"), ("solarizedTheme", "solarized-theme"), ("vimImproved", "vim-improved"),
            ("sessionsReworked", "sessions-reworked"), ("projectWork", "project-work"), ("search", "search"))
        for export, name in imports:
            source += f'import {{ {export} }} from {json.dumps(str(PROFILE / "plugins" / (name + ".js")))};\n'
        source += '''
plugins.use(solarizedTheme);
plugins.use(vimImproved);
plugins.use(yukeDashboard);
plugins.use({ name: "dashboard-test", apply(ctx) {
  ctx.inject(["tui", "composer-vim"], c => {
    c.tui.status.add({ render: () => "DASHBOARD TEST READY" });
    let laterTitle = null, laterHint = null;
    c.tui.keymap.add({
      f4: () => { const pane = currentPane(); laterHint = new Text(); pane.hint = laterHint; c.tui.root.invalidate(); },
      f5: () => { const pane = currentPane(); laterTitle = new Text({ text: "OTHER TITLE" }); pane.title = laterTitle; c.tui.root.invalidate(); },
      f6: () => plugins.dispose("yuke-dashboard"),
      f7: () => plugins.use(yukeDashboard),
      f9: "window:split-right",
      f10: "focus:left",
      f11: "window:close",
      f12: "focus:right",
      f8: () => {
        const pane = currentPane();
        c.print("DASHBOARD_PROBE " + JSON.stringify({
          text: pane?.composer?.text, session: pane?.session.sessionId, paneX: pane?.rect.x, focus: pane?.focus, title: pane?.title.text, otherHint: pane?.hint === laterHint,
          mode: c["composer-vim"].mode(pane?.composer || null),
          drawUnchanged: pane?.draw === ChatView.prototype.draw,
          layoutUnchanged: pane?.layout === ChatView.prototype.layout,
        }));
      },
    });
  });
}});
'''
        if MINIMAL_PROFILE:
            source = source.replace("plugins.use(solarizedTheme);\nplugins.use(vimImproved);", "plugins.use(composerVim);")
        elif FULL_PROFILE:
            source = f'import {{ profile }} from {json.dumps(str(PROFILE / "profile.js"))};\n' + source
            source = source.replace("plugins.use(solarizedTheme);\nplugins.use(vimImproved);\nplugins.use(yukeDashboard);", "plugins.use(profile);")
        (profile / "index.js").write_text(source)
        (profile / "providers.json").write_text(json.dumps({"providers": [{
            "id": "dashboard-test", "base_url": f"http://127.0.0.1:{server.server_port}/v1",
            "endpoints": [{"protocol": "openai_chat"}],
            "models": [{"id": "model", "upstream_id": "model", "limits": {"context_window": 100000, "max_output_tokens": 4096}}],
        }]}))
        (profile / "providers.json").chmod(0o600)
        environment = {"HOME": str(root), "PATH": os.environ["PATH"], "SHELL": "/bin/bash", "TERM": "xterm-256color", "YUKE_APPNAME": "yuke"}
        for key in ("CONFIG", "DATA", "STATE", "CACHE"):
            environment[f"XDG_{key}_HOME"] = str(root / key.lower())
        run = root / "run.sh"
        run.write_text("#!/bin/sh\ncd " + shlex.quote(str(workspace)) + "\nexec /usr/bin/env -i " +
                       " ".join(shlex.quote(f"{key}={value}") for key, value in environment.items()) + " " + shlex.quote(YUKE) + "\n")
        run.chmod(0o700)

        def start():
            tmux("new-session", "-d", "-x", "120", "-y", "40", "-s", "test", str(run))
            expect("startup", "DASHBOARD TEST READY", "Resume a session", "dashboard-workspace")

        def probe():
            log = root / "state/yuke/yuke.log"
            before = log.read_text().count("DASHBOARD_PROBE ")
            keys("F8")
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                entries = [line.split("DASHBOARD_PROBE ", 1)[1] for line in log.read_text().splitlines() if "DASHBOARD_PROBE " in line]
                if len(entries) > before:
                    return json.loads(entries[-1])
                time.sleep(0.05)
            raise AssertionError("probe did not run")

        start()
        if MINIMAL_PROFILE:
            assert probe()["mode"] == "normal"
            literal("i")
            assert probe()["mode"] == "insert"
            keys("C-n")
            assert probe()["mode"] == "normal"
            literal("m")
            expect("minimal model action", "type to filter", "dashboard-test")
            keys("Enter")
            expect("minimal model selected", "model · dashboard-test/model", absent=("type to filter",))
            literal("c")
            expect("minimal commands action", "/cache", "prompt cache")
            keys("Escape")
            probe()
            literal("i")
            literal("minimal prompt r s w m c q")
            assert probe()["text"] == "minimal prompt r s w m c q"
            keys("Enter")
            expect("minimal first send", "Dashboard test reply.", absent=("Resume a session",))
            assert len(REQUESTS) == 1 and not ERRORS, ERRORS
            keys("C-q")
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline and tmux("has-session", "-t", "test", check=False).returncode == 0:
                time.sleep(0.05)
            assert tmux("has-session", "-t", "test", check=False).returncode != 0, "minimal profile did not exit"
            print("Minimal bundled-Vim profile passed")
            raise SystemExit(0)
        if FULL_PROFILE:
            expect("full profile actions", "Choose a model", "Search chats and files", "Project tasks and checkpoints", absent=("new chat",))
        else:
            expect("optional plugins absent", "Choose a model", "Commands", absent=("Search chats and files", "Project tasks and checkpoints", "new chat"))
        assert probe()["mode"] == "normal"
        literal("i")
        keys("F9")
        expect("new split starts normal", "Resume a session")
        assert probe()["mode"] == "normal"
        keys("F10")
        returned = probe()
        assert returned["paneX"] == 0, returned
        assert returned["mode"] == "insert", f"pane focus changed an explicit insert mode: {returned}"
        keys("F12")
        assert probe()["paneX"] > 0
        literal("i")
        keys("C-n")
        fresh = probe()
        assert fresh["mode"] == "normal", f"new empty draft did not enter normal mode: {fresh}"
        keys("F11", "Escape")
        assert probe()["mode"] == "normal"
        literal("dm")
        assert probe()["text"] == ""
        expect("pending Vim operator owns dashboard letter", "Resume a session", absent=("type to filter",))
        keys("Escape")
        probe()
        keys("Tab")
        assert probe()["focus"] == "transcript"
        literal("m")
        expect("transcript owns dashboard letter", "Resume a session", absent=("type to filter",))
        keys("Escape")
        probe()
        keys("Tab")
        assert probe()["focus"] == "composer"
        literal("m")
        expect("normal letter model shortcut", "type to filter", "dashboard-test")
        keys("Escape")
        keys("M-m")
        expect("Alt binding removed", "Resume a session", absent=("type to filter",))
        assert probe()["text"] == ""
        literal("i")
        literal("safe unsent draft r s w m c q")
        expect("plain typing", "safe unsent draft r s w m c q")
        assert probe()["text"] == "safe unsent draft r s w m c q"
        keys("Escape")
        literal("m")
        expect("draft keeps dashboard keys inactive", "safe unsent draft r s w m c q", absent=("type to filter",))
        keys("Escape")
        assert probe()["text"] == "safe unsent draft r s w m c q"
        literal("ggd$")
        cleared = probe()
        assert cleared["text"] == "" and cleared["mode"] == "normal", cleared
        literal("m")
        expect("normal-mode clearing restores dashboard keys", "type to filter")
        keys("Escape")
        literal("i")
        literal("safe unsent draft r s w m c q")
        keys("Escape")
        keys("F6")
        expect("unload restores hint and draft", "new chat", "type a message to start the session", "safe unsent draft r s w m c q", absent=("Resume a session",))
        keys("F7")
        expect("reload preserves draft", "Resume a session", "safe unsent draft r s w m c q", absent=("new chat",))
        assert probe()["text"] == "safe unsent draft r s w m c q"
        keys("F5", "F6")
        assert probe()["title"] == "OTHER TITLE", "unload must preserve another plugin's title"
        keys("F7", "F4", "F6")
        restored = probe()
        assert restored["title"] == "OTHER TITLE" and restored["otherHint"], restored
        keys("F7")
        literal("i")
        keys("C-e", "C-u", "Escape")
        literal("m")
        expect("model shortcut", "type to filter", "dashboard-test")
        keys("Escape")
        expect("model cancel preserves composer", "Resume a session", absent=("type to filter",))
        assert probe()["text"] == ""
        literal("m")
        keys("Enter")
        expect("model context updates", "model · dashboard-test/model", absent=("type to filter",))
        screen = expect("clickable model action", "Choose a model")
        lines = screen.splitlines()
        row = next(i for i, line in enumerate(lines) if "Choose a model" in line)
        col = lines[row].index("Choose a model")
        literal(f"\x1b[<0;{col + 2};{row + 1}M\x1b[<0;{col + 2};{row + 1}m")
        expect("mouse action", "type to filter")
        keys("Escape")
        literal("c")
        expect("command palette", "/cache", "prompt cache")
        keys("Escape")
        literal("i")
        literal("dashboard first prompt")
        keys("Enter")
        expect("first send replaces dashboard", "Dashboard test reply.", absent=("Resume a session", "Choose a model"))
        assert len(REQUESTS) == 1
        saved = probe()
        assert saved["session"] and saved["text"] == ""
        assert saved["drawUnchanged"] and saved["layoutUnchanged"], saved
        assert not ERRORS, ERRORS
        if FULL_PROFILE:
            keys("C-q")
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline and tmux("has-session", "-t", "test", check=False).returncode == 0:
                time.sleep(0.05)
            assert tmux("has-session", "-t", "test", check=False).returncode != 0, "full profile did not exit"
            print("Full-profile normal-mode keys, insert typing, unload/reload, and first prompt passed")
            raise SystemExit(0)
        keys("Escape")
        literal("m")
        expect("dashboard key inactive in a saved chat", "Dashboard test reply.", absent=("type to filter",))
        keys("Escape")
        assert probe()["mode"] == "normal"
        keys("C-n")
        expect("new chat restores dashboard", "Resume a session", "model · dashboard-test/model", absent=("Dashboard test reply.",))
        keys("Escape")
        literal("r")
        expect("session browser", "sessions", "dashboard-workspace", "type to filter")
        keys("Enter")
        expect("resume hides dashboard", "Dashboard test reply.", absent=("Resume a session",))
        assert probe()["session"] == saved["session"]
        assert len(REQUESTS) == 1, "resume must not call a model"
        keys("C-n")
        literal("i/panel vsplit")
        keys("Enter")
        expect("split panes", "Resume a session")
        assert tmux("capture-pane", "-t", "test", "-p").stdout.count("Resume a session") == 2
        literal("i/panel close")
        keys("Enter")
        expect("close split", "Resume a session")
        tmux("resize-window", "-t", "test", "-x", "42", "-y", "16")
        expect("compact dashboard", "YUKE", "Resume a session", "Choose a model")
        assert probe()["mode"] == "insert", "returning to the original pane must preserve insert mode"
        literal("compact draft")
        expect("compact typing", "compact draft")
        assert probe()["text"] == "compact draft"
        tmux("resize-window", "-t", "test", "-x", "120", "-y", "40")
        expect("resize keeps draft", "compact draft", "Resume a session")
        keys("C-q")
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and tmux("has-session", "-t", "test", check=False).returncode == 0:
            time.sleep(0.05)
        assert tmux("has-session", "-t", "test", check=False).returncode != 0, "Ctrl+Q did not exit"

        (profile / "index.js").write_text(source.replace("plugins.use(yukeDashboard);", "plugins.use(sessionsReworked);\nplugins.use(projectWork);\nplugins.use(search);\nplugins.use(yukeDashboard);", 1))
        start()
        expect("optional actions present", "Search chats and files", "Project tasks and checkpoints")
        keys("Escape")
        literal("w")
        expect("real work shortcut", "Work · dashboard-workspace", "No project goal saved")
        keys("Escape")
        literal("s")
        expect("real search shortcut", "Search ·", "dashboard-fixture.txt")
        literal("w")
        expect("modal owns dashboard keys", "Search ·", absent=("Work · dashboard-workspace",))
        keys("Escape")
        expect("search cancel returns to dashboard", "Resume a session", absent=("Search ·",))
        assert probe()["text"] == ""
        literal("r")
        expect("real sessions shortcut", "Sessions", "dashboard first prompt")
        keys("Escape")
        assert len(REQUESTS) == 1, "startup actions must not call a model"
        assert not ERRORS, ERRORS
        assert probe()["mode"] == "normal"
        literal("q")
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and tmux("has-session", "-t", "test", check=False).returncode == 0:
            time.sleep(0.05)
        assert tmux("has-session", "-t", "test", check=False).returncode != 0, "dashboard q did not exit"
finally:
    tmux("kill-server", check=False)
    server.shutdown()
    server.server_close()
    with tempfile.NamedTemporaryFile(prefix="yuke-dashboard-", suffix=".txt", mode="w", delete=False) as artifact:
        artifact.write("\n".join(CAPTURES))
        print("Saved dashboard captures:", artifact.name)

print("Dashboard detached-tmux checks passed")
