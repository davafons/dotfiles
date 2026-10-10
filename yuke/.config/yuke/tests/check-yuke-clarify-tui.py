#!/usr/bin/env python3
"""Detached tmux check: real keys, real SQLite, mocked engine delivery only."""
import json
import pathlib
import shutil
import subprocess
import tempfile
import time
import uuid

TMUX = shutil.which("tmux")
YUKE = shutil.which("yuke")
assert TMUX and YUKE, "tmux and yuke are required"
ROOT = pathlib.Path(__file__).resolve().parents[1]
SESSION = "yuke-clarify-" + uuid.uuid4().hex[:10]
captures = []


def tmux(*args, check=True):
    return subprocess.run([TMUX, *args], check=check, text=True, capture_output=True)


def screen(label, expected, timeout=7):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        output = tmux("capture-pane", "-t", SESSION, "-p").stdout
        if expected in output:
            captures.append(f"=== {label} ===\n{output}")
            return output
        time.sleep(0.05)
    raise AssertionError(f"{label}: wanted {expected!r}\n{output}")


def send(*keys, literal=None):
    if literal is not None:
        tmux("send-keys", "-t", SESSION, "-l", literal)
    else:
        tmux("send-keys", "-t", SESSION, *keys)


try:
    with tempfile.TemporaryDirectory(prefix="yuke-clarify-tui-") as directory:
        root = pathlib.Path(directory)
        profile = root / "config/yuke"
        (profile / "plugins").mkdir(parents=True)
        helper = ROOT / "plugins/yuke-clarify-store.py"
        (profile / "plugins/yuke-clarify-store.py").symlink_to(helper)
        database = root / "state/yuke/clarify/questions.sqlite3"

        def store(action, args=None):
            return json.loads(subprocess.check_output(["python3", str(helper), str(database), action, json.dumps(args or {})], text=True))

        for number, (title, options, origin) in enumerate([
            ("Deployment target", [{"label": "Local", "description": "Simplest setup", "recommended": True}, {"label": "Server", "description": "Remote access", "recommended": False}], "origin"),
            ("Project name", [], "origin"), ("Dangerous action", [], "origin"), ("Other chat question", [], "another"),
        ]):
            store("add", {"site": f"{origin}:{number}:1", "session": origin,
                          "question": {"title": title, "question": title + "?", "context": "This answer determines the next step.", "options": options}})
        receipts = root / "receipts.json"
        fixture = f'''
import {{ plugins, client, fs }} from "yuke";
import {{ currentPane }} from "yuke:session";
import {{ yukeClarify }} from {json.dumps(str(ROOT / "plugins/yuke-clarify.js"))};
import {{ vimImproved }} from {json.dumps(str(ROOT / "plugins/vim-improved.js"))};
plugins.use(vimImproved);
let clarify = plugins.use(yukeClarify);
plugins.use({{ name: "clarify-fixture", apply(ctx) {{
  ctx.inject(["tui", "composer-vim"], (c) => {{
    const pane = currentPane();
    pane.session.sessionId = "origin";
    const receipts = [];
    let fail = false;
    let reloads = 0;
    client.sessionSendInput = async (id, content) => {{
      await new Promise((resolve) => setTimeout(resolve, 150));
      if (fail) {{ fail = false; throw new Error("fixture refused input"); }}
      receipts.push({{ id, content, draft: pane.composer.text, caret: pane.composer.input.caret }});
      await fs.writeFile({json.dumps(str(receipts))}, JSON.stringify(receipts));
      return {{ input_id: "fixture-" + receipts.length, reason: "active_run" }};
    }};
    c.tui.keymap.add({{
      f6: () => {{ pane.session.sessionId = pane.session.sessionId === "origin" ? "another" : "origin"; c.tui.root.invalidate(); }},
      f7: () => {{ fail = true; }},
      f8: () => {{ pane.focusRegion("transcript"); }},
      f9: () => {{ pane.focusRegion("composer"); }},
      f10: async () => {{ await clarify.dispose(); clarify = plugins.use(yukeClarify); reloads++; c.tui.root.invalidate(); }},
      f11: () => {{ pane.composer.text = ""; pane.focusRegion("composer"); c["composer-vim"].setMode(pane.composer, "normal"); c.tui.root.invalidate(); }},
    }});
    c.tui.status.add({{ side: "right", render: () => "CARET " + pane.composer.input.caret + " CHAT " + pane.session.sessionId + " RELOAD " + reloads }});
    c.tui.root.invalidate();
  }});
}} }});
'''
        (profile / "index.js").write_text(fixture)
        run = root / "run.sh"
        run.write_text("#!/bin/sh\n" + "\n".join(f"export XDG_{name}_HOME={json.dumps(str(root / folder))}" for name, folder in [("CONFIG", "config"), ("STATE", "state"), ("DATA", "data"), ("CACHE", "cache")]) + f"\nexport TERM=xterm-256color\ncd {json.dumps(str(root))}\nexec {json.dumps(YUKE)}\n")
        run.chmod(0o700)
        tmux("new-session", "-d", "-x", "110", "-y", "32", "-s", SESSION, "-n", "Agent Tests yuke-clarify", str(run))
        screen("quiet queue", "3 questions")
        send("i")
        send(literal="unsent draft")
        send("Left", "Left")
        before = screen("draft and caret", "CARET 10")
        assert "INSERT" in before
        send(literal="\x1b[1;2D")
        opened = screen("Shift+Left from insert", "Deployment target · 1/3")
        assert "Local (recommended)" in opened and "Simplest setup" in opened
        send("Down", "Down", "Enter")
        send(literal="half an answer")
        screen("custom answer draft", "half an answer")
        send("Escape")
        closed = screen("Escape keeps question and composer", "3 questions")
        assert "unsent draft" in closed and "CARET 10" in closed and "INSERT" in closed
        # Persisted question and answer draft survive an actual process restart.
        time.sleep(0.4)
        tmux("kill-session", "-t", SESSION)
        tmux("new-session", "-d", "-x", "110", "-y", "32", "-s", SESSION, "-n", "Agent Tests yuke-clarify", str(run))
        screen("restart restores queue", "3 questions")
        send("i")
        send(literal="unsent draft")
        send("Left", "Left")
        screen("restored fixture draft", "CARET 10")
        send("F10")
        screen("plugin reload completed", "RELOAD 1")
        send(literal="\x1b[1;2D")
        screen("restart and reload preserve answer", "half an answer")
        send("C-b", "Up", "Enter", "Enter")
        screen("choice advances exactly once", "Project name · 1/2")
        records = json.loads(receipts.read_text())
        assert len(records) == 1 and records[0]["id"] == "origin"
        assert "User answer: Server" in records[0]["content"][0]["text"]
        assert records[0]["draft"] == "unsent draft" and records[0]["caret"] == 10
        send(literal="partial project")
        send("Tab")
        screen("Tab next", "Dangerous action · 2/2")
        send("BTab")
        screen("Shift+Tab restores text", "partial project")
        send("Escape")
        screen("close before delivery failure", "2 questions")
        send("F7")
        send(literal="\x1b[1;2D")
        screen("reopened free text", "partial project")
        send("Enter")
        screen("delivery failure retained", "fixture refused input")
        assert len(json.loads(receipts.read_text())) == 1
        send("Enter")
        screen("retry succeeds", "Dangerous action · 1/1")
        send("C-d")
        screen("explicit decline confirmation", "Decline this question?")
        send("Escape")
        screen("cancel decline", "Dangerous action?")
        send("C-d", "Enter")
        screen("all answered without touching composer", "CARET 10")
        time.sleep(0.4)
        records = json.loads(receipts.read_text())
        assert len(records) == 3 and all(record["id"] == "origin" for record in records)
        assert ": dismissed]" in records[2]["content"][0]["text"]
        assert "Do not treat this as approval" in records[2]["content"][0]["text"]
        assert [entry["session"] for entry in store("list")] == ["another"]
        send("Escape")
        screen("normal mode after answering", "NORMAL")
        send("F6")
        screen("other session queue", "1 question")
        send("F8")
        send(literal="\x1b[1;2D")
        screen("Shift+Left from transcript", "Other chat question · 1/1")
        send("Escape", "F9")
        screen("composer survives session navigation", "unsent draft")
        send("Escape")
        send(literal="\x1b[1;2D")
        screen("Shift+Left from normal mode", "Other chat question · 1/1")
        send("Escape")
        # Slash-command fallback and the empty-inbox path, without a provider call.
        send("F11")
        screen("empty fixture composer", "CARET 0")
        send(literal="/")
        send(literal="questions")
        send("Enter")
        screen("slash-command inbox", "Other chat question · 1/1")
        send(literal="answer in the other chat")
        send("Enter")
        time.sleep(0.4)
        assert json.loads(receipts.read_text())[-1]["id"] == "another"
        send(literal="\x1b[1;2D")
        screen("empty-inbox notification", "No pending questions in this chat.")
finally:
    tmux("kill-session", "-t", SESSION, check=False)
    with tempfile.NamedTemporaryFile(prefix="yuke-clarify-tui-", suffix=".txt", mode="w", delete=False) as artifact:
        artifact.write("\n".join(captures))
        print("Saved clarification TUI captures:", artifact.name)
print("Clarification TUI check passed")
