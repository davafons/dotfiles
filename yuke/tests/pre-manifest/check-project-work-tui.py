#!/usr/bin/env python3
"""Exercise work capture, stale checkpoints, draft safety, and restart in detached tmux."""
import argparse
import http.server
import json
import os
import re
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import threading
import time
import uuid

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--colors", choices=["truecolor", "256"], default="truecolor")
parser.add_argument("--background", choices=["dark", "light"], default="dark")
ARGS = parser.parse_args()
PALETTES = {
    ("truecolor", "dark"): [(70, 149, 247), (65, 199, 185), (219, 179, 45), (183, 162, 232), (117, 185, 56), (8, 43, 52)],
    ("truecolor", "light"): [(0, 101, 153), (0, 111, 102), (118, 92, 0), (114, 75, 158), (59, 107, 20), (253, 246, 227)],
    ("256", "dark"): [(75,), (80,), (179,), (183,), (113,), (234,)],
    ("256", "light"): [(24,), (23,), (58,), (60,), (22,), (230,)],
}
COLORS = PALETTES[(ARGS.colors, ARGS.background)]

TMUX = shutil.which("tmux")
YUKE = shutil.which("yuke")
assert TMUX and YUKE, "tmux and yuke are required"
PLUGIN = Path(__file__).resolve().parents[1] / "plugins/project-work.js"
HELPER = PLUGIN.with_name("project-work-store.py")
SOCKET = "yuke-work-" + uuid.uuid4().hex[:10]
captures = []
requests = []
server_errors = []


def tmux(*args, check=True):
    return subprocess.run([TMUX, "-L", SOCKET, *args], check=check, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def wait_screen(label, predicate, timeout=15):
    deadline = time.monotonic() + timeout
    screen = ""
    while time.monotonic() < deadline:
        screen = tmux("capture-pane", "-t", "test", "-p").stdout
        if predicate(screen):
            captures.append(f"=== {label} ===\n{screen}")
            return screen
        time.sleep(0.05)
    raise AssertionError(f"timed out: {label}\n{screen}\nserver errors: {server_errors}")


def send(text):
    tmux("send-keys", "-t", "test", "-l", text)
    tmux("send-keys", "-t", "test", "Enter")


def expect_color(label, value, fg, bg=None):
    styled = tmux("capture-pane", "-t", "test", "-p", "-e").stdout
    foreground = background = None
    matches = []
    for token in re.finditer(r"\x1b\[([\d;]*)m|([^\x1b]+)", styled):
        if token.group(1) is None:
            content = token.group(2)
            matches.append(content if foreground == fg and (bg is None or background == bg) else "\0" * len(content))
            continue
        codes = [int(code or 0) for code in token.group(1).split(";")]
        index = 0
        while index < len(codes):
            code = codes[index]
            if code == 0:
                foreground = background = None
            elif code == 39:
                foreground = None
            elif code == 49:
                background = None
            elif code in (38, 48) and index + 2 < len(codes):
                size = 3 if codes[index + 1] == 2 else 1
                color = tuple(codes[index + 2:index + 2 + size])
                if code == 38:
                    foreground = color
                else:
                    background = color
                index += size + 1
            index += 1
    captures.append(f"=== {label} ANSI colors ===\n{styled}")
    assert value in "".join(matches), f"missing expected colors for {value!r}: foreground={fg}, background={bg}"


class Provider(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        try:
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append(body)
            assert self.path == "/v1/chat/completions", self.path
            messages = body["messages"]
            last = messages[-1]
            args = None
            if last["role"] == "user":
                content = last["content"]
                if "seed work" in str(content):
                    args = {"action": "list", "kind": "issues"}
                    assert any(tool["function"]["name"] == "github_work" for tool in body["tools"])
                    assert any(tool["function"]["name"] == "project_work" for tool in body["tools"])
            elif last["role"] == "tool":
                output = json.loads(last["content"])
                if "items" in output:
                    args = {"action": "get", "kind": "issues", "number": 17}
                elif "item" in output:
                    args = {"action": "task", "title": "Fix session focus", "status": "later", "notes": "Keep user's global key handler", "github_url": output["item"]["url"]}
                elif "id" in output:
                    args = {"action": "checkpoint", "task_id": output["id"], "summary": "Focused test passes", "next_step": "Run the full suite", "verification": "Full suite has not run"}
                elif "session" in output:
                    args = {"action": "context", "version": 0, "goal": "Reliable session navigation", "notes": "Keep the global key handler"}
            if args:
                tool_name = "github_work" if args["action"] == "get" and "number" in args or args["action"] == "list" and "kind" in args else "project_work"
                delta = {"tool_calls": [{"index": 0, "id": "call-" + str(len(requests)), "type": "function", "function": {"name": tool_name, "arguments": json.dumps(args)}}]}
                finish = "tool_calls"
            else:
                delta = {"content": "Work seed complete." if last["role"] == "tool" else "Work continued without a new checkpoint."}
                finish = "stop"
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            for event in (
                {"id": "work-test", "choices": [{"index": 0, "delta": delta, "finish_reason": None}]},
                {"id": "work-test", "choices": [{"index": 0, "delta": {}, "finish_reason": finish}]},
            ):
                self.wfile.write(("data: " + json.dumps(event) + "\n\n").encode())
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        except Exception as error:
            server_errors.append(repr(error))
            self.send_error(500)


server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Provider)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
try:
    with tempfile.TemporaryDirectory(prefix="yuke-work-tui-") as directory:
        root = Path(directory).resolve()
        workspace = root / "repo"
        workspace.mkdir()
        profile = root / "config/yuke"
        (profile / "plugins").mkdir(parents=True)
        (profile / "plugins/project-work-store.py").symlink_to(HELPER)
        (profile / "plugins/project-work-github.py").symlink_to(PLUGIN.with_name("project-work-github.py"))
        fake_bin = root / "bin"
        fake_bin.mkdir()
        (fake_bin / "gh").symlink_to(Path(__file__).resolve().with_name("work-github-fixture.py"))
        (profile / "index.js").write_text(
            'import { plugins, defineConfig } from "yuke";\n'
            f'defineConfig({{ colors: {json.dumps(ARGS.colors)} }});\n'
            f'import {{ projectWork }} from {json.dumps(str(PLUGIN))};\n'
            'import { currentPane } from "yuke:session";\n'
            f'import {{ solarizedTheme }} from {json.dumps(str(PLUGIN.with_name("solarized-theme.js")))};\n'
            'plugins.use(solarizedTheme);\n'
            'plugins.use(projectWork);\n'
            'plugins.use({name: "work-test-ready", apply(ctx) { ctx.inject(["tui"], c => {\n'
            '  c.tui.status.add({render: () => "WORK TEST READY"});\n'
            '  c.tui.command.add("probe", {run: () => c.print("WORK_PROBE " + JSON.stringify({text: currentPane()?.composer?.input.text, session: currentPane()?.session.sessionId}))});\n'
            '  c.tui.keymap.add({"ctrl+y": "work-test-ready:probe"});\n'
            '}); }});\n'
        )
        (profile / "providers.json").write_text(json.dumps({"providers": [{
            "id": "work-test", "base_url": f"http://127.0.0.1:{server.server_port}/v1",
            "endpoints": [{"protocol": "openai_chat"}],
            "models": [{"id": "model", "upstream_id": "model", "limits": {"context_window": 100000, "max_output_tokens": 4096}}],
        }]}))
        (profile / "providers.json").chmod(0o600)
        environment = {"HOME": str(root), "PATH": str(fake_bin) + os.pathsep + os.environ["PATH"], "SHELL": "/bin/bash", "TERM": "xterm-256color", "YUKE_APPNAME": "yuke"}
        environment["GH_FIXTURE_LOG"] = str(root / "github-requests.jsonl")
        environment["GH_FIXTURE_SLOW_FILE"] = str(root / "slow-github")
        for key in ("CONFIG", "DATA", "STATE", "CACHE"):
            environment[f"XDG_{key}_HOME"] = str(root / key.lower())
        run = root / "run.sh"
        run.write_text("#!/bin/sh\ncd " + shlex.quote(str(workspace)) + "\nexec /usr/bin/env -i " +
                       " ".join(shlex.quote(f"{key}={value}") for key, value in environment.items()) + " " + shlex.quote(YUKE) + "\n")
        run.chmod(0o700)

        def start():
            tmux("new-session", "-d", "-x", "140", "-y", "45", "-s", "test", str(run))
            wait_screen("ready", lambda screen: "WORK TEST READY" in screen)
            background = "ffff/ffff/ffff" if ARGS.background == "light" else "0000/0000/0000"
            tmux("send-keys", "-t", "test", "-l", "\x1b]11;rgb:" + background + "\x1b\\")

        def probe():
            log = root / "state/yuke/yuke.log"
            before = log.read_text().count("WORK_PROBE ") if log.exists() else 0
            tmux("send-keys", "-t", "test", "C-y")
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                lines = [line.split("WORK_PROBE ", 1)[1] for line in log.read_text().splitlines() if "WORK_PROBE " in line]
                if len(lines) > before:
                    return json.loads(lines[-1])
                time.sleep(0.05)
            raise AssertionError("composer probe did not run")

        database = root / "state/yuke/work/work.sqlite3"

        def snapshot():
            return json.loads(subprocess.check_output(["python3", str(HELPER), str(database), json.dumps(
                {"action": "list", "root": str(workspace), "session": "", "include_done": True})], text=True))

        start()
        send("/model work-test/model")
        wait_screen("local test model selected", lambda screen: "work-test/model" in screen)
        send("/todo Deferred before a saved session")
        wait_screen("task captured in a draft", lambda screen: "Task saved for later" in screen)
        send("/work")
        wait_screen("work in an unsaved conversation", lambda screen: "Work · repo" in screen and "Show done" in screen)
        tmux("send-keys", "-t", "test", "d")
        wait_screen("completed-task toggle works in a draft", lambda screen: "Work · repo" in screen and "Hide done" in screen)
        tmux("send-keys", "-t", "test", "Escape")
        send("seed work")
        wait_screen("agent saved task, checkpoint, and context", lambda screen: "Work seed complete." in screen)
        data = snapshot()
        assert len(data["tasks"]) == 2 and len(data["checkpoints"]) == 1, data
        assert data["context"]["goal"] == "Reliable session navigation"
        assert not data["checkpoints"][0]["stale"], "a checkpoint saved during this run must be fresh"
        saved_session = data["checkpoints"][0]["session"]
        send("/work")
        wait_screen("project overview", lambda screen: "Work · repo" in screen and "Run the full suite" in screen and "Later (2)" in screen and "Fix session focus" in screen)
        board = tmux("capture-pane", "-t", "test", "-p").stdout
        assert board.splitlines()[0].startswith("Work · repo"), "work must occupy the full terminal, not a centered panel"
        assert "WORK TEST READY" not in board, "a full view must cover the chat status bar"
        lines = board.splitlines()
        explanation_row = next(i for i, line in enumerate(lines) if "LATER · SELECTED TASK" in line)
        page_row = next(i for i, line in enumerate(lines) if "1–2 / 2" in line)
        assert explanation_row > page_row, "the selected task explanation must sit below the full-width board"
        assert lines[explanation_row].index("LATER · SELECTED TASK") <= 1, "the explanation must not occupy a right sidebar"
        for index, label in enumerate(["Now (0)", "Later (2)", "Blocked (0)", "Review (0)", "Done (0)"]):
            expect_color("kanban " + label, label, COLORS[index])
        expect_color("selected card contrast", "> Fix", COLORS[5], COLORS[1])
        tmux("send-keys", "-t", "test", "Enter")
        wait_screen("task details", lambda screen: "Fix session focus" in screen and "Prepare a brief" in screen and "Full suite has not run" in screen)
        tmux("send-keys", "-t", "test", "Enter")
        wait_screen("brief prepared without sending", lambda screen: "Next step: Run the full suite" in screen and "Work · repo" not in screen)
        brief = probe()
        assert "Continue project task" in brief["text"] and "Verify the checkout" in brief["text"]
        assert brief["session"] == saved_session
        assert len(requests) == 6, "preparing work must not send a model request"
        tmux("send-keys", "-t", "test", "C-e", "C-u")
        assert probe()["text"] == ""
        send("continue work without checkpoint")
        wait_screen("second run ended", lambda screen: "Work continued without a new checkpoint." in screen)
        send("/work")
        wait_screen("stale checkpoint warning", lambda screen: "STALE" in screen)
        tmux("send-keys", "-t", "test", "C-d")
        wait_screen("scroll task explanation", lambda screen: "Run the full suite" in screen)
        tmux("send-keys", "-t", "test", "Enter")
        wait_screen("task status controls", lambda screen: "Set status: blocked" in screen)
        tmux("send-keys", "-t", "test", "Down", "Down", "Down", "Down", "Down", "Down", "Enter")
        wait_screen("task marked blocked", lambda screen: "Work · repo" in screen and "BLOCKED · SELECTED TASK" in screen and "Fix session focus" in screen)
        assert next(task for task in snapshot()["tasks"] if task["title"] == "Fix session focus")["status"] == "blocked"
        tmux("send-keys", "-t", "test", "Escape")
        tmux("send-keys", "-t", "test", "-l", "keep this unsent draft")
        # Use the command palette so opening /work does not consume the draft.
        tmux("send-keys", "-t", "test", "C-p")
        tmux("send-keys", "-t", "test", "-l", "project tasks")
        tmux("send-keys", "-t", "test", "Enter")
        wait_screen("work opened over an unsent draft", lambda screen: "Work · repo" in screen)
        tmux("send-keys", "-t", "test", "Escape")
        wait_screen("draft survives closing work", lambda screen: "keep this unsent draft" in screen and "Work · repo" not in screen)
        assert len(requests) == 7
        # A process restart must not erase local work. Do not attach to this tmux server.
        tmux("kill-session", "-t", "test")
        start()
        send("/work")
        wait_screen("work survives restart", lambda screen: "Work · repo" in screen and "STALE" in screen and "BLOCKED · SELECTED TASK" in screen and "Fix session focus" in screen)
        assert snapshot()["checkpoints"][0]["session"] == saved_session
        tmux("send-keys", "-t", "test", "Escape")
        tmux("send-keys", "-t", "test", "-l", "restart draft")
        tmux("send-keys", "-t", "test", "C-p")
        tmux("send-keys", "-t", "test", "-l", "project tasks")
        tmux("send-keys", "-t", "test", "Enter")
        wait_screen("work over restart draft", lambda screen: "Work · repo" in screen)
        tmux("send-keys", "-t", "test", "Enter")
        wait_screen("resume action", lambda screen: "Open linked session" in screen and "Prepare a brief" in screen)
        tmux("send-keys", "-t", "test", "Down", "Enter")
        wait_screen("resume refuses to discard a draft", lambda screen: "unsent draft" in screen and "Work · repo" in screen)
        tmux("send-keys", "-t", "test", "Escape")
        wait_screen("restart draft retained", lambda screen: "restart draft" in screen and "Work · repo" not in screen)
        assert probe() == {"text": "restart draft", "session": None}
        tmux("send-keys", "-t", "test", "C-e", "C-u")
        send("/work")
        wait_screen("work ready to resume", lambda screen: "Work · repo" in screen)
        tmux("send-keys", "-t", "test", "Enter")
        wait_screen("linked session action", lambda screen: "Open linked session" in screen and "Prepare a brief" in screen)
        tmux("send-keys", "-t", "test", "Down", "Enter")
        wait_screen("original conversation resumed", lambda screen: "Work seed complete." in screen and "Work · repo" not in screen)
        assert probe()["session"] == saved_session
        assert len(requests) == 7, "resuming a conversation must not start another run"
        for index in range(7):
            subprocess.check_output(["python3", str(HELPER), str(database), json.dumps({"action": "task", "root": str(workspace), "session": saved_session,
                "title": f"Active task {index}", "status": "now", "notes": "Check the current revision"})], text=True)
        for status, title in (("review", "改善导航 🧭"), ("done", "Verified cleanup")):
            subprocess.check_output(["python3", str(HELPER), str(database), json.dumps({"action": "task", "root": str(workspace), "session": saved_session,
                "title": title, "status": status, "notes": "Review this result"})], text=True)
        send("/work")
        wait_screen("board columns populated", lambda screen: "Now (7)" in screen and "NOW · SELECTED TASK" in screen)
        tmux("send-keys", "-t", "test", "n")
        wait_screen("next column page", lambda screen: "6–7 / 7" in screen)
        tmux("send-keys", "-t", "test", "p")
        wait_screen("previous column page", lambda screen: "1–5 / 7" in screen)
        tmux("send-keys", "-t", "test", "2")
        wait_screen("project context tab", lambda screen: "PROJECT GOAL" in screen and "DECISIONS" in screen and "Run the full suite" in screen)
        expect_color("active context tab", " 2 Context ", COLORS[5], COLORS[0])
        tmux("send-keys", "-t", "test", "3")
        checkpoint_view = wait_screen("checkpoints tab", lambda screen: "WHERE YOU STOPPED" in screen and "Full suite has not run" in screen)
        checkpoint_lines = checkpoint_view.splitlines()
        checkpoint_row = next(i for i, line in enumerate(checkpoint_lines) if "WHERE YOU STOPPED" in line)
        assert checkpoint_lines[checkpoint_row].index("WHERE YOU STOPPED") <= 1, "checkpoint explanations must also start below the cards"
        tmux("send-keys", "-t", "test", "1")
        tmux("resize-window", "-t", "test", "-x", "50", "-y", "24")
        wait_screen("narrow active column", lambda screen: "[Now]" in screen and "Now (7)" in screen)
        tmux("send-keys", "-t", "test", "Right", "Right", "Right")
        wait_screen("narrow column navigation", lambda screen: "[Review]" in screen and "改善导航 🧭" in screen)
        tmux("send-keys", "-t", "test", "/")
        wait_screen("task filter input", lambda screen: "Filter project tasks" in screen)
        send("改善")
        wait_screen("filter searches the project", lambda screen: "Filter: 改善" in screen and "Review (1)" in screen and " · working" not in screen)
        tmux("send-keys", "-t", "test", "/")
        wait_screen("clear filter input", lambda screen: "Filter project tasks" in screen)
        tmux("send-keys", "-t", "test", "Enter")
        wait_screen("filter cleared", lambda screen: "[Review]" in screen and "Filter: 改善" not in screen and " · working" not in screen)
        tmux("send-keys", "-t", "test", "Right", "d")
        wait_screen("completed cards visible", lambda screen: "[Done]" in screen and "Verified cleanup" in screen)
        tmux("resize-window", "-t", "test", "-x", "140", "-y", "45")
        wait_screen("wide layout restored", lambda screen: "DONE · SELECTED TASK" in screen and "Now (7)" in screen)
        tmux("send-keys", "-t", "test", "-l", "\x1b[<0;14;2M\x1b[<0;14;2m")
        wait_screen("mouse tab navigation", lambda screen: "PROJECT GOAL" in screen and "DECISIONS" in screen)
        tmux("send-keys", "-t", "test", "4")
        wait_screen("GitHub issues and linked inner task", lambda screen: "example/repo · issues (23)" in screen and "INNER TASKS (1)" in screen and "Read-only remote body" in screen)
        tmux("send-keys", "-t", "test", "n")
        wait_screen("GitHub cursor page", lambda screen: "page 2" in screen and "Issue 119" in screen and " · working" not in screen)
        tmux("send-keys", "-t", "test", "p")
        wait_screen("GitHub previous page", lambda screen: "page 1" in screen and "INNER TASKS (1)" in screen and " · working" not in screen)
        tmux("send-keys", "-t", "test", "v")
        wait_screen("PR review and CI details", lambda screen: "Review focus PR" in screen and "CHANGES_REQUESTED" in screen and "FAILURE" in screen and "test · FAILURE" in screen and " · working" not in screen)
        tmux("send-keys", "-t", "test", "o")
        wait_screen("closed PR filter includes merged", lambda screen: "MERGED" in screen and " · closed" in screen and " · working" not in screen)
        tmux("send-keys", "-t", "test", "v")
        wait_screen("closed issues", lambda screen: "issues (23) · closed" in screen and " · working" not in screen)
        tmux("send-keys", "-t", "test", "o")
        wait_screen("all issues", lambda screen: "issues (23) · all" in screen and " · working" not in screen)
        tmux("send-keys", "-t", "test", "o")
        wait_screen("issues restored", lambda screen: "issues (23) · open" in screen and "INNER TASKS (1)" in screen and " · working" not in screen)
        tmux("send-keys", "-t", "test", "a")
        wait_screen("linked task input", lambda screen: "Internal step for GitHub #17" in screen)
        send("Add focused regression")
        wait_screen("new linked inner step", lambda screen: "INNER TASKS (2)" in screen and "Add focused regression" in screen and " · working" not in screen)
        linked = next(task for task in snapshot()["tasks"] if task["title"] == "Add focused regression")
        assert linked["github_url"] == "https://github.com/example/repo/issues/17" and linked["status"] == "later"
        gh_commands = [json.loads(line) for line in (root / "github-requests.jsonl").read_text().splitlines()]
        assert all(command[:2] in (["repo", "view"], ["api", "graphql"]) for command in gh_commands)
        assert not any("mutation" in " ".join(command) for command in gh_commands)
        tmux("send-keys", "-t", "test", "q")
        wait_screen("full view closes", lambda screen: "WORK TEST READY" in screen and "Work · repo" not in screen)
        assert probe()["session"] == saved_session
        assert len(requests) == 7, "work navigation must not send model requests"
        (root / "slow-github").touch()
        send("/work")
        wait_screen("reopened work", lambda screen: "Work · repo" in screen)
        tmux("send-keys", "-t", "test", "4")
        pid_file = root / "slow-github.pid"
        deadline = time.monotonic() + 5
        while not pid_file.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert pid_file.exists(), "the slow fixture read must start"
        gh_pid = int(pid_file.read_text())
        tmux("send-keys", "-t", "test", "q")
        wait_screen("close cancels GitHub read", lambda screen: "WORK TEST READY" in screen and "Work · repo" not in screen)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            state = subprocess.run(["ps", "-p", str(gh_pid), "-o", "stat="], text=True, capture_output=True).stdout.strip()
            if not state or state.startswith("Z"):
                break
            time.sleep(0.05)
        else:
            os.kill(gh_pid, 9)
            raise AssertionError("closing work left a gh request running")
        assert not server_errors, server_errors
finally:
    tmux("kill-server", check=False)
    server.shutdown()
    server.server_close()
    thread.join()
    with tempfile.NamedTemporaryFile(prefix="yuke-work-tui-", suffix=".txt", mode="w", delete=False) as artifact:
        artifact.write("\n".join(captures))
        print("Saved work TUI captures:", artifact.name)

print(f"Project work TUI checks passed ({ARGS.colors}/{ARGS.background}, full board, colors, navigation, narrow layout, draft safety, restart)")
