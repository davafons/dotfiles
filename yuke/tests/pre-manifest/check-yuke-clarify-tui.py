#!/usr/bin/env python3
"""Detached tmux check: real keys, real SQLite, mocked engine delivery only."""
import json
import pathlib
import re
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


def screen(label, expected, timeout=7, absent=()):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        output = tmux("capture-pane", "-t", SESSION, "-p").stdout
        if expected in output and all(value not in output for value in absent):
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
            context = "Long context line\n" * 35 + "END OF LONG CONTEXT" if origin == "another" else "This answer determines the next step."
            store("add", {"site": f"{origin}:{number}:1", "session": origin,
                          "question": {"title": title, "question": title + "?", "context": context, "options": options}})
        receipts = root / "receipts.json"
        fixture = f'''
import {{ plugins, client, fs }} from "yuke";
import {{ currentPane }} from "yuke:session";
import {{ yukeClarify }} from {json.dumps(str(ROOT / "plugins/yuke-clarify.js"))};
import {{ vimImproved }} from {json.dumps(str(ROOT / "plugins/vim-improved.js"))};
import {{ solarizedTheme }} from {json.dumps(str(ROOT / "plugins/solarized-theme.js"))};
plugins.use(solarizedTheme);
plugins.use(vimImproved);
let clarify = plugins.use(yukeClarify);
plugins.use({{ name: "clarify-fixture", apply(ctx) {{
  ctx.inject(["tui", "composer-vim"], (c) => {{
    const pane = currentPane();
    pane.session.sessionId = "origin";
    c.on("chat.strip", () => [{{ text: "queued fixture input", group: "UIDim" }}, {{ text: "working fixture prompt", group: "UIDim" }}]);
    const receipts = [];
    let fail = false;
    let reloads = 0;
    let leftMoves = 0;
    c.tui.command.add("focus:left", {{ run: () => {{ leftMoves++; c.tui.root.invalidate(); }} }});
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
      f12: () => {{ pane.session.sessionId = "multi"; c.tui.root.invalidate(); }},
    }});
    c.tui.status.add({{ side: "right", render: () => "CARET " + pane.composer.input.caret + " CHAT " + pane.session.sessionId + " RELOAD " + reloads + " FOCUS " + pane.focus + " LEFT " + leftMoves }});
    c.tui.root.invalidate();
  }});
}} }});
'''
        (profile / "index.js").write_text(fixture)
        run = root / "run.sh"
        run.write_text("#!/bin/sh\n" + "\n".join(f"export XDG_{name}_HOME={json.dumps(str(root / folder))}" for name, folder in [("CONFIG", "config"), ("STATE", "state"), ("DATA", "data"), ("CACHE", "cache")]) + f"\nexport TERM=xterm-256color\nexport COLORTERM=truecolor\ncd {json.dumps(str(root))}\nexec {json.dumps(YUKE)}\n")
        run.chmod(0o700)
        tmux("new-session", "-d", "-x", "110", "-y", "32", "-s", SESSION, "-n", "Agent Tests yuke-clarify", str(run))
        stacked = screen("quiet queue", "3 questions")
        for number, title in enumerate(["Deployment target", "Project name", "Dangerous action"], 1):
            assert f"{number}) {title}" in stacked
        assert stacked.index("queued fixture input") < stacked.index("working fixture prompt") < stacked.index("Questions waiting for response")
        assert stacked.index("3) Dangerous action") < stacked.index("─" * 20), "questions must sit above the prompt rule"
        send("i")
        send(literal="unsent draft")
        send("Left", "Left")
        before = screen("draft and caret", "CARET 10")
        assert "INSERT" in before

        def mouse(row, button=0):
            send(literal=f"\x1b[<{button};4;{row + 1}M\x1b[<{button};4;{row + 1}m")
            time.sleep(0.15)

        banner_lines = before.splitlines()
        for label in ["queued fixture input", "working fixture prompt", "unsent draft"]:
            mouse(next(i for i, line in enumerate(banner_lines) if label in line))
            screen("click outside questions leaves inbox closed", "CARET 10", absent=("Deployment target · 1/3",))
        banner_top = next(i for i, line in enumerate(banner_lines) if "Questions waiting for response" in line)
        mouse(banner_top, button=2)
        screen("right click leaves inbox closed", "CARET 10", absent=("Deployment target · 1/3",))
        for label in ["Questions waiting for response", "2) Project name", "Answer when ready"]:
            mouse(next(i for i, line in enumerate(banner_lines) if label in line))
            screen("banner click opens inbox: " + label, "Deployment target · 1/3")
            assert not receipts.exists(), "opening the inbox must not submit an answer"
            send("Escape")
            preserved = screen("banner click preserves draft and caret", "CARET 10", absent=("Deployment target · 1/3",))
            assert "unsent draft" in preserved and "INSERT" in preserved
        send(literal="\x1b[104;5u")
        opened = screen("Ctrl+H from insert", "Deployment target · 1/3")
        assert "LEFT 0" in opened, "pending questions must take priority over pane navigation"
        send("Escape")
        screen("Ctrl+H preserves draft", "CARET 10", absent=("Deployment target · 1/3",))
        send("C-h")
        screen("legacy backspace remains an edit", "unsent drft", absent=("Deployment target · 1/3",))
        send(literal="a")
        screen("restore draft after backspace", "CARET 10")
        send(literal="\x1b[1;2D")
        opened = screen("Shift+Left still opens inbox", "Deployment target · 1/3")
        assert "1) Local" in opened and "recommended" in opened and "Simplest setup" in opened
        assert "2) Server" in opened and "3) Other…" in opened
        lines = opened.splitlines()
        top = next(i for i, line in enumerate(lines) if "┌─1) Deployment target" in line)
        bottom = next(i for i, line in enumerate(lines) if "└" in line)
        assert bottom - top + 1 == 15, "choice picker must fit header + responses, without blank filler"
        colored = tmux("capture-pane", "-t", SESSION, "-e", "-p").stdout
        captures.append("=== colored choice picker ===\n" + colored)
        selected = next(line for line in colored.splitlines() if "1) Local" in line)
        unselected = next(line for line in colored.splitlines() if "2) Server" in line)
        assert re.search(r"\x1b\[[0-9;:]*m", selected), "selected row must have actual terminal styles"
        assert "›" in selected and "›" not in unselected
        assert re.search(r"(?:48[;:]|;4[0-7](?:;|m))", selected), "selected row needs a background highlight"
        detail = next(line for line in colored.splitlines() if "Simplest setup" in line)
        assert "48;2;70;149;247" in selected and "48;2;70;149;247" in detail, "both selected rows must use the theme's solid blue accent"
        assert "48;2;70;149;247" not in unselected
        send("Down", "Down", "Enter")
        send(literal="half an answer")
        screen("custom answer draft", "half an answer")
        send(literal="\x1b[104;5u")
        modal = screen("Ctrl+H stays with the open modal", "Deployment target · 1/3")
        assert "LEFT 0" in modal and "half an answer" in modal
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
        compact = screen("choice advances exactly once", "Project name · 1/2")
        lines = compact.splitlines()
        top = next(i for i, line in enumerate(lines) if "┌─1) Project name" in line)
        bottom = next(i for i, line in enumerate(lines) if "└" in line)
        assert bottom - top + 1 == 10, "free-text picker must shrink to its one-row answer editor"
        records = json.loads(receipts.read_text())
        assert len(records) == 1 and records[0]["id"] == "origin"
        assert "User answer: Server" in records[0]["content"][0]["text"]
        assert records[0]["draft"] == "unsent draft" and records[0]["caret"] == 10
        send(literal="partial project")
        send(literal="\x1b[13;2u")
        send(literal="second line")
        screen("multiline answer editor", "second line")
        send("Tab")
        screen("Tab next", "Dangerous action · 2/2")
        send("BTab")
        restored = screen("Shift+Tab restores text", "partial project")
        assert "second line" in restored
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
        assert "partial project\nsecond line" in records[1]["content"][0]["text"]
        assert ": dismissed]" in records[2]["content"][0]["text"]
        assert "Do not treat this as approval" in records[2]["content"][0]["text"]
        assert [entry["session"] for entry in store("list")] == ["another"]
        send("Escape")
        screen("normal mode after answering", "NORMAL")
        send(literal="\x1b[104;5u")
        screen("no-question Ctrl+H retains navigation", "LEFT 1")
        send("F6")
        screen("other session queue", "1 question")
        send("F8")
        send(literal="\x1b[1;2D")
        screen("Shift+Left from transcript", "Other chat question · 1/1")
        send("Escape")
        screen("transcript ready for Ctrl+H", "FOCUS transcript", absent=("Other chat question · 1/1",))
        send(literal="\x1b[104;5u")
        screen("Ctrl+H from transcript", "Other chat question · 1/1")
        send("NPage", "NPage", "NPage")
        screen("scroll long question context", "END OF LONG CONTEXT")
        send("PPage", "PPage", "PPage")
        screen("scroll context back to question", "Other chat question?")
        send("Escape")
        time.sleep(0.15)
        send("F9")
        restored = screen("composer focus restored", "FOCUS composer")
        assert "unsent draft" in restored
        send("Escape")
        send(literal="\x1b[1;2D")
        screen("Shift+Left from normal mode", "Other chat question · 1/1")
        send("Escape")
        screen("normal mode ready for Ctrl+H", "NORMAL", absent=("Other chat question · 1/1",))
        send(literal="\x1b[104;5u")
        screen("Ctrl+H from normal mode", "Other chat question · 1/1")
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
        screen("last answer closes inbox", "CHAT another",
               absent=("Other chat question · 1/1", "1 question ·"))
        assert json.loads(receipts.read_text())[-1]["id"] == "another"
        send(literal="\x1b[1;2D")
        screen("empty-inbox notification", "No pending questions in this chat.")
        store("add", {"site": "another:many:1", "session": "another", "question": {
            "title": "Many choices", "question": "Which response?", "context": "Every response should fit.",
            "options": [{"label": f"Choice {n}", "description": f"Description {n}", "recommended": n == 1} for n in range(1, 9)],
        }})
        send(literal="\x1b[1;2D")
        full = screen("all eight responses plus Other fit", "9) Other…")
        assert all(f"{n}) Choice {n}" in full for n in range(1, 9))
        lines = full.splitlines()
        top = next(i for i, line in enumerate(lines) if "┌─1) Many choices" in line)
        bottom = next(i for i, line in enumerate(lines) if "└" in line)
        assert bottom - top + 1 == 27
        tmux("resize-window", "-t", SESSION, "-x", "80", "-y", "14")
        time.sleep(0.2)
        send("Down", "Down", "Down", "Down", "Down", "Down", "Down", "Down")
        narrow = screen("small terminal scrolls to final response", "9) Other…")
        assert "Many choices" in narrow and "esc later" in narrow
        send("Escape")
        tmux("resize-window", "-t", SESSION, "-x", "110", "-y", "32")
        store("add", {"site": "another:simple:1", "session": "another", "question": {
            "title": "Simple choices", "question": "Choose yes or no?", "context": "",
            "options": [{"label": label, "description": "", "recommended": False} for label in ["Yes", "No"]],
        }})
        send(literal="\u001b[1;2D")
        screen("reopen before simple choices", "Many choices · 1/2")
        send("Tab")
        simple = screen("description-free choices use single rows", "Simple choices · 2/2")
        lines = simple.splitlines()
        top = next(i for i, line in enumerate(lines) if "┌─2) Simple choices" in line)
        bottom = next(i for i, line in enumerate(lines) if "└" in line)
        assert bottom - top + 1 == 10, "choices without descriptions must not reserve empty description rows"
        assert "1) Yes" in simple and "2) No" in simple and "3) Other…" in simple
        send("Escape")
        screen("simple picker closed", "CHAT another", absent=("Simple choices · 2/2",))
        send("F12")
        screen("multi-select fixture session", "CHAT multi")
        send(literal="never sent")
        screen("main draft before multi-select", "never sent")
        telemetry = {"title": "Telemetry", "question": "Which telemetry should we add?", "context": "Choose several.", "multi_select": True,
                     "options": [{"label": label, "description": "", "recommended": number == 0} for number, label in enumerate(["Logging", "Metrics", "Tracing"])]}
        store("add", {"site": "multi:1:1", "session": "multi", "question": telemetry})
        def multi_pending():
            return [item for item in store("list") if item["session"] == "multi"]

        screen("new multi-select queue visible", "1 question ·")
        before_multi = len(json.loads(receipts.read_text()))
        send(literal="\x1b[104;5u")
        opened = screen("checkbox picker starts without defaults", "[ ] 1) Logging")
        assert "[x]" not in opened
        send(literal="13")
        checked = screen("number keys toggle independent choices", "[x] 3) Tracing")
        assert "[x] 1) Logging" in checked and "[ ] 2) Metrics" in checked
        send(literal="3")
        screen("number key toggles off", "[ ] 3) Tracing")
        send(literal=" ")
        screen("Space toggles current choice", "[x] 3) Tracing")
        send("Escape")
        screen("checkbox draft closed", "never sent", absent=("Telemetry · 1/1",))
        send("F10")
        screen("checkbox plugin reload", "RELOAD 2")
        send(literal="\x1b[104;5u")
        restored = screen("checkboxes persist across reload", "[x] 3) Tracing")
        assert "[x] 1) Logging" in restored
        send(literal="4")
        send("Enter")
        send(literal="Audit events")
        custom = screen("custom answer alongside checked options", "Audit events")
        assert "[x] 1) Logging" in custom and "[x] 3) Tracing" in custom
        send("C-b", "Enter")
        screen("multi-select delivered and closed", "never sent", absent=("Telemetry · 1/1",))
        records = json.loads(receipts.read_text())
        assert len(records) == before_multi + 1 and records[-1]["id"] == "multi"
        values = json.loads(records[-1]["content"][0]["text"].split("Structured answers: ")[1])["answers"]
        assert values == ["Logging", "Tracing", "user_note: Audit events"]
        assert records[-1]["draft"] == "never sent"

        store("add", {"site": "multi:2:1", "session": "multi", "question": {**telemetry, "title": "Notes"}})
        screen("new notes question visible", "1 question ·")
        send(literal="\x1b[104;5u")
        screen("multi-select empty guard fixture", "Notes · 1/1")
        send("Enter")
        screen("empty checkbox answer cannot approve default", "Select at least one option")
        send(literal="2")
        send("C-e")
        send(literal="Production only")
        screen("notes alongside checkbox choice", "Production only")
        send("Enter")
        screen("notes delivered", "never sent", absent=("Notes · 1/1",))
        records = json.loads(receipts.read_text())
        values = json.loads(records[-1]["content"][0]["text"].split("Structured answers: ")[1])["answers"]
        assert values == ["Metrics", "user_note: Production only"]

        questions = [
            {**telemetry, "title": "Features", "question_id": "features"},
            {"title": "Target", "question_id": "target", "question": "Where should this run?", "context": "", "multi_select": False,
             "options": [{"label": "Local", "description": "", "recommended": True}, {"label": "Server", "description": "", "recommended": False}]},
            {"title": "Reason", "question_id": "reason", "question": "Why this setup?", "context": "", "options": [], "multi_select": False},
        ]
        batch = store("add_batch", {"site": "multi:batch:1", "session": "multi", "questions": questions})
        before_batch = len(records)
        screen("batch queue visible", "3 questions ·")
        send("F7")
        send(literal="\x1b[104;5u")
        screen("batch first question", "Features · 1/3")
        send(literal="12")
        send("Tab")
        send(literal="Use both")
        send("Enter")
        screen("batch Enter stages rather than sending", "Target · 2/3")
        assert len(json.loads(receipts.read_text())) == before_batch
        assert multi_pending()[0]["draft"]["committed"]
        send(literal="2")
        send(literal="Behind VPN")
        screen("typing from options opens notes", "Behind VPN")
        send("Enter")
        screen("batch free text question", "Reason · 3/3")
        send("Enter")
        review = screen("review shows unanswered question", "Review answers · 2/3 ready")
        assert "Unanswered (not approval)" in review and "Logging; Metrics" in review
        assert len(json.loads(receipts.read_text())) == before_batch
        send("Enter")
        screen("unanswered confirmation before any send", "Submit with 1 unanswered question?")
        send("Escape")
        screen("cancel unanswered submission", "Review answers · 2/3 ready")
        send(literal="3")
        screen("review number reopens question", "Reason · 3/3")
        send(literal="Ops requested it")
        send("Enter")
        screen("complete batch review", "Review answers · 3/3 ready")
        send("Enter")
        screen("batch engine failure stays retryable", "fixture refused input")
        assert len(json.loads(receipts.read_text())) == before_batch
        assert all(item["status"] == "pending" for item in multi_pending())
        send("Enter")
        screen("batch retry submits one input", "never sent", absent=("Review clarification answers",))
        records = json.loads(receipts.read_text())
        assert len(records) == before_batch + 1, "a batch sends exactly one user input, not one per question"
        payload = records[-1]["content"][0]["text"]
        structured = json.loads(payload.split("Structured answers:\n")[1].split("\n\n")[0])["answers"]
        assert structured == {"features": {"answers": ["Logging", "Metrics", "user_note: Use both"]},
                              "target": {"answers": ["Server", "user_note: Behind VPN"]},
                              "reason": {"answers": ["user_note: Ops requested it"]}}
        assert batch["id"] in payload and "NOT approval" in payload
        assert multi_pending() == []

        store("add_batch", {"site": "multi:batch:2", "session": "multi", "questions": [questions[0], questions[2]]})
        screen("partial batch queue visible", "2 questions ·")
        send(literal="\x1b[104;5u")
        screen("skip confirmation fixture", "Features · 1/2")
        send("Enter")
        screen("empty multi-select stages as unanswered", "Reason · 2/2")
        send(literal="Only this answer")
        send("Enter")
        screen("partial batch review", "Review answers · 1/2 ready")
        send("Enter")
        screen("explicitly confirm unanswered batch", "Submit with 1 unanswered question?")
        send("Enter")
        screen("confirmed partial batch delivered", "never sent", absent=("Review clarification answers",))
        payload = json.loads(receipts.read_text())[-1]["content"][0]["text"]
        structured = json.loads(payload.split("Structured answers:\n")[1].split("\n\n")[0])["answers"]
        assert structured["features"]["answers"] == [] and structured["reason"]["answers"] == ["user_note: Only this answer"]
        assert "Unanswered / skipped (not approval)" in payload
        assert multi_pending() == []
finally:
    tmux("kill-session", "-t", SESSION, check=False)
    with tempfile.NamedTemporaryFile(prefix="yuke-clarify-tui-", suffix=".txt", mode="w", delete=False) as artifact:
        artifact.write("\n".join(captures))
        print("Saved clarification TUI captures:", artifact.name)
print("Clarification TUI check passed")
