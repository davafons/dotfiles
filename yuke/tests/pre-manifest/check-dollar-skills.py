#!/usr/bin/env python3
"""Check $skill completion and real input delivery in an isolated detached TUI."""
import http.server
import json
import os
import pathlib
import shlex
import shutil
import sqlite3
import subprocess
import tempfile
import threading
import time
import uuid

YUKE = os.environ.get("YUKE_BIN") or shutil.which("yuke")
TMUX = shutil.which("tmux")
assert YUKE and TMUX, "yuke and tmux are required"
source = pathlib.Path(__file__).resolve().parents[1]
socket = "yuke-dollar-skills-" + uuid.uuid4().hex[:10]
requests = []
captures = []
errors = []


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_POST(self):
        try:
            request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append(request)
            events = [{"choices": [{"index": 0, "delta": {"content": "SKILL_ACK_" + str(len(requests))}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 10, "completion_tokens": 5}}, "[DONE]"]
            payload = "".join("data: " + (event if isinstance(event, str) else json.dumps(event)) + "\n\n" for event in events).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except Exception as error:
            errors.append(repr(error))


server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()


def mux(*args, check=True):
    return subprocess.run([TMUX, "-L", socket, *args], text=True, capture_output=True, check=check)


def screen(label):
    capture = mux("capture-pane", "-p", "-t", "test", "-S", "-35").stdout
    captures.append(f"=== {label} ===\n{capture}")
    return capture


def wait(label, text, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        capture = screen(label)
        if text in capture:
            return capture
        captures.pop()
        time.sleep(0.05)
    raise AssertionError(f"{label}: missing {text!r}\n{capture}")


def keys(*values):
    mux("send-keys", "-t", "test", *values)


def text(value):
    keys("-l", value)


def user_text(request):
    content = [message for message in request["messages"] if message["role"] == "user"][-1]["content"]
    return content if isinstance(content, str) else "".join(part.get("text", "") for part in content)


try:
    with tempfile.TemporaryDirectory(prefix="yuke-dollar-skills-") as directory:
        root = pathlib.Path(directory).resolve()
        home = root / "home"
        profile = root / "config/yuke"
        (profile / "plugins").mkdir(parents=True)
        home.mkdir()
        work = root / "work"
        work.mkdir()

        def skill(scope, folder, contents):
            path = scope / ".agents/skills" / folder / "SKILL.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(contents)
            return path

        alpha_body = "---\nname: alpha\ndescription: >-\n  Workspace alpha\n  description.\n---\nWORKSPACE_ALPHA_BODY\nUse scripts/check.py.\n"
        alpha = skill(work, "not-the-name", alpha_body)
        skill(home, "alpha", "---\nname: alpha\ndescription: Global alpha\n---\nGLOBAL_ALPHA_MUST_NOT_LOAD\n")
        beta = skill(home, "beta", "---\nname: 'beta'\ndescription: \"Beta \\u0073kill\"\n---\nGLOBAL_BETA_BODY\n")
        alias = work / ".agents/skills/alias"
        alias.symlink_to(beta.parent, target_is_directory=True)
        skill(work, "invalid", "---\nname: Invalid\ndescription: Must not complete\n---\nINVALID\n")
        for filename in ("dollar-skills.py",):
            (profile / "plugins" / filename).symlink_to(source / "plugins" / filename)
        native = root / "native-skills.json"
        (profile / "tools").mkdir()
        shutil.copyfile(source / "plugins/profile-reloader.js", profile / "plugins/profile-reloader.js")
        (profile / "plugins/dollar-skills.js").symlink_to(source / "plugins/dollar-skills.js")
        (profile / "profile.js").write_text(
            'import { dollarSkills } from "./plugins/dollar-skills.js";\n'
            'export const profile = { name: "user-profile", apply(ctx) { ctx.use(dollarSkills); } };\n'
        )
        (profile / "index.js").write_text(
            'import { plugins, client, fs } from "yuke";\n'
            'import { currentPane } from "yuke:session";\n'
            f'import {{ dollarSkills }} from {json.dumps(str(source / "plugins/dollar-skills.js"))};\n'
            'import { profileReloader } from "./plugins/profile-reloader.js";\n'
            'plugins.use(profileReloader);\n'
            'plugins.use({ name: "skill-test", apply(ctx) {\n'
            f'  ctx.hook("prompt.build", async build => {{ await fs.writeFile({json.dumps(str(native))}, JSON.stringify(build.skills)); }});\n'
            '  ctx.inject(["tui"], c => {\n'
            '    c.tui.status.add({ side: "left", render: () => "SKILL TEST READY" });\n'
            '    c.tui.keymap.add({ "ctrl+t": () => { currentPane().composer.text = "before $al after"; currentPane().composer.input.caret = 10; }, "ctrl+y": () => { currentPane().composer.text = ""; }, "ctrl+o": () => { plugins.dispose("dollar-skills"); }, "ctrl+r": () => { plugins.use(dollarSkills); } });\n'
            '    client.catalogList(null).then(catalog => { currentPane().session.setModel(catalog.models.find(model => model.selector === "skills-fixture/test"), ""); });\n'
            '  });\n'
            '}});\n'
        )
        providers = profile / "providers.json"
        providers.write_text(json.dumps({"providers": [{"id": "skills-fixture", "base_url": f"http://127.0.0.1:{server.server_port}/v1", "endpoints": [{"protocol": "openai_chat"}], "models": [{"id": "test", "upstream_id": "test", "limits": {"context_window": 100000, "max_output_tokens": 1000}}]}]}))
        providers.chmod(0o600)
        environment = {"HOME": str(home), "XDG_CONFIG_HOME": str(root / "config"), "XDG_DATA_HOME": str(root / "data"), "XDG_STATE_HOME": str(root / "state"), "XDG_CACHE_HOME": str(root / "cache"), "YUKE_APPNAME": "yuke", "TERM": "xterm-256color"}
        runner = root / "run.sh"
        runner.write_text("#!/bin/sh\n" + "\n".join(f"export {key}={shlex.quote(value)}" for key, value in environment.items()) + "\nunset HERDR_ENV HERDR_PANE_ID HERDR_SOCKET_PATH AI_AGENT CLAUDECODE\n" + f"cd {shlex.quote(str(work))}\nexec {shlex.quote(YUKE)}\n")
        runner.chmod(0o700)
        mux("-f", "/dev/null", "new-session", "-d", "-x", "110", "-y", "35", "-s", "test", str(runner))
        wait("startup", "skills-fixture/test")

        text("$")
        capture = wait("all skills", "$beta")
        assert "$alpha" in capture and "Workspace alpha description." in capture
        assert "Global alpha" not in capture and "$Invalid" not in capture
        keys("Escape")
        time.sleep(0.1)
        capture = screen("dismissed menu")
        assert "Workspace alpha description." not in capture
        keys("C-y")
        text("$")
        wait("menu navigation", "$beta")
        keys("Down", "Enter")
        wait("arrow selection", "› $beta")
        assert not requests, "arrow selection sent the draft"
        keys("C-y")
        text("Please $al")
        wait("filtered skill", "Workspace alpha description.")
        keys("Enter")
        capture = wait("Enter inserts without sending", "Please $alpha")
        assert not requests, "completion sent the draft"
        text("now and $be")
        wait("second skill", "Beta skill")
        keys("Tab")
        text("and $alpha ")
        keys("Enter")
        wait("expanded first input", "SKILL_ACK_1")
        sent = user_text(requests[-1])
        assert sent.count('skill_content name="alpha"') == 1 and sent.count('skill_content name="beta"') == 1, sent
        assert "WORKSPACE_ALPHA_BODY" in sent and "GLOBAL_BETA_BODY" in sent
        assert "GLOBAL_ALPHA_MUST_NOT_LOAD" not in sent and "name: alpha" not in sent
        assert "Please $alpha now and $beta and $alpha" in sent
        assert "</skill_content>\n\nPlease" in sent
        assert str(beta.parent) in sent, "relative paths did not use the canonical skill directory"
        database = next((root / "data/yuke").rglob("*.db"))
        with sqlite3.connect(database) as db:
            saved = json.loads(db.execute("SELECT payload FROM events WHERE name='message.committed' AND json_extract(payload, '$.type')='user' ORDER BY seq LIMIT 1").fetchone()[0])
        assert saved.get("skill_names") == ["alpha", "beta"], saved
        capture = screen("native folded skills")
        assert "skills · alpha, beta" in capture and "Please $alpha" in capture, capture
        assert "WORKSPACE_ALPHA_BODY" not in capture and "GLOBAL_BETA_BODY" not in capture, capture
        usage = json.loads(subprocess.check_output(["python3", str(source / "plugins/usage-data.py"), str(database)], text=True))
        assert {item["name"]: item["invocations"] for item in usage["skills"]} == {"alpha": 1, "beta": 1}, usage["skills"]
        actual_catalog = json.loads(native.read_text())
        expected_catalog = json.loads(subprocess.check_output(["python3", str(source / "plugins/dollar-skills.py"), "scan", str(work)], env={**os.environ, "HOME": str(home)}, text=True))
        assert [(entry["name"], entry["description"], entry["location"]) for entry in actual_catalog] == [(entry["name"], entry["description"], entry["path"]) for entry in expected_catalog], (actual_catalog, expected_catalog)

        keys("C-t")
        text("x")
        keys("BSpace")
        wait("middle token menu", "Workspace alpha description.")
        keys("Tab")
        wait("preserved suffix", "before $alpha after")
        keys("C-y")
        text(r"Literal $unknown costs $20; `$alpha` and \$beta and $$alpha.")
        keys("Enter")
        wait("literal input", "SKILL_ACK_2")
        assert "<skill_content" not in user_text(requests[-1])

        skill(work, "new-skill", "---\nname: new-skill\ndescription: Added after creation\n---\nNEW_BODY\n")
        text("Use $new-skill ")
        keys("Enter")
        wait("stored session catalog", "SKILL_ACK_3")
        assert "NEW_BODY" not in user_text(requests[-1]), "a live scan replaced the session snapshot"

        keys("C-y")
        text("/reload")
        wait("context reload command", "reload profile plugins, AGENTS.md, and skills")
        keys("Enter")
        database = next((root / "data/yuke").rglob("*.db"))
        deadline = time.monotonic() + 10
        refreshed = False
        while time.monotonic() < deadline:
            with sqlite3.connect(database) as db:
                refreshed = db.execute("SELECT COUNT(*) FROM session_skills WHERE name='new-skill'").fetchone()[0] > 0
            if refreshed:
                break
            time.sleep(0.05)
        assert refreshed, "context reload did not save the new skill"
        keys("C-y")
        text("$new-")
        wait("completion follows context reload", "Added after creation")
        keys("Tab")
        wait("new skill completion", "› $new-skill")
        keys("C-y")

        alpha.unlink()
        text("Use $alpha ")
        keys("Enter")
        wait("unreadable skill restores draft", "send failed")
        capture = screen("failed input retained")
        assert "Use $alpha" in capture and len(requests) == 3, "a partial expansion was sent"
        alpha.write_text(alpha_body)
        keys("C-y")
        text("$al")
        wait("menu before unload", "Workspace alpha description.")
        keys("C-o")
        time.sleep(0.1)
        assert "Workspace alpha description." not in screen("unload closes menu")
        keys("C-y")
        text("Use $alpha ")
        keys("Enter")
        wait("unload removes input hook", "SKILL_ACK_4")
        assert "<skill_content" not in user_text(requests[-1])
        keys("C-r")
        text("$al")
        wait("reloaded plugin", "Workspace alpha description.")
        keys("Right")
        text("x")
        wait("caret routing after menu close", "$alx")
        for stroke in ("C-a", "C-e"):
            keys("C-y")
            text("Please $alpha")
            wait("menu before " + stroke, "Workspace alpha description.")
            keys(stroke)
            time.sleep(0.1)
            assert "Workspace alpha description." not in screen("caret key closes menu: " + stroke), "caret movement left the skill menu open"
            expected = len(requests) + 1
            keys("Enter")
            wait("Enter sends after " + stroke, "SKILL_ACK_" + str(expected))
        keys("C-y")
        text("/skill:alpha compatibility")
        expected = len(requests) + 1
        keys("Enter")
        wait("single native skill compatibility", "SKILL_ACK_" + str(expected))
        with sqlite3.connect(database) as db:
            saved = json.loads(db.execute("SELECT payload FROM events WHERE name='message.committed' AND json_extract(payload, '$.type')='user' ORDER BY seq DESC LIMIT 1").fetchone()[0])
        assert saved.get("skill_name") == "alpha" and not saved.get("skill_names"), saved
        usage = json.loads(subprocess.check_output(["python3", str(source / "plugins/usage-data.py"), str(database)], text=True))
        assert {item["name"]: item["invocations"] for item in usage["skills"]} == {"alpha": 4, "beta": 1}, usage["skills"]
        assert not errors, errors
finally:
    mux("kill-server", check=False)
    server.shutdown()
    with tempfile.NamedTemporaryFile(prefix="yuke-dollar-skills-", suffix=".txt", mode="w", delete=False) as artifact:
        artifact.write("\n".join(captures))
        print("Saved skill test transcript:", artifact.name)

print("$skill completion and delivery checks passed")
