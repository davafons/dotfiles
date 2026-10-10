#!/usr/bin/env python3
"""Drive /context in a detached TUI with an isolated store and local provider."""
import argparse
import http.server
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import tempfile
import threading
import time
import uuid

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--colors", choices=["truecolor", "256"], default="truecolor")
parser.add_argument("--background", choices=["dark", "light"], default="dark")
parser.add_argument("--full-profile", action="store_true")
args = parser.parse_args()
PROFILE = Path(__file__).resolve().parents[1]
YUKE = os.environ.get("YUKE_TEST_BINARY") or shutil.which("yuke")
TMUX = shutil.which("tmux")
assert YUKE and TMUX
SOCKET = "yuke-context-" + uuid.uuid4().hex[:10]
CAPTURES = []
REQUESTS = []
COLORS = {
    ("truecolor", "dark"): {"tools": (65, 199, 185), "system": (183, 162, 232), "skills": (219, 179, 45), "chat": (117, 185, 56)},
    ("truecolor", "light"): {"tools": (0, 111, 102), "system": (114, 75, 158), "skills": (118, 92, 0), "chat": (59, 107, 20)},
    ("256", "dark"): {"tools": (80,), "system": (183,), "skills": (179,), "chat": (113,)},
    ("256", "light"): {"tools": (23,), "system": (60,), "skills": (58,), "chat": (22,)},
}[(args.colors, args.background)]


def mux(*values, check=True):
    return subprocess.run([TMUX, "-L", SOCKET, *values], check=check, text=True, capture_output=True)


def expect(label, *words, absent=()):
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline:
        screen = mux("capture-pane", "-t", "test", "-p").stdout
        if all(word in screen for word in words) and all(word not in screen for word in absent):
            CAPTURES.append(f"=== {label} ===\n{screen}")
            return screen
        time.sleep(0.05)
    CAPTURES.append(f"=== FAILED {label} ===\n{screen}")
    raise AssertionError(f"{label}: missing {words}, excluded {absent}\n{screen}")


def grid_fills_width(label, screen, side_by_side=False):
    glyphs = "■□▧"
    rows = []
    legend_column = None
    if side_by_side:
        heading = next((line.split("│")[1] for line in screen.splitlines() if "Context grid" in line and "Context breakdown" in line and "│" in line), None)
        assert heading is not None, f"{label}: grid and legend must have adjacent columns"
        legend_column = heading.index("Context breakdown")
        assert any("System + plugin instructions" in line and any(glyph in line.split("│")[1][:legend_column] for glyph in glyphs) for line in screen.splitlines() if "│" in line), f"{label}: legend must align beside grid cells"
    for line in screen.splitlines():
        parts = line.split("│")
        if len(parts) < 3:
            continue
        inside = parts[1][:legend_column] if side_by_side else parts[1]
        if inside.strip() and all(char in glyphs + " " for char in inside):
            rows.append(inside)
    assert rows, f"{label}: grid is missing"
    assert sum(char in glyphs for row in rows for char in row) == 200, f"{label}: grid must conserve 200 squares"
    last = max(index for index, char in enumerate(rows[0]) if char in glyphs)
    assert last >= len(rows[0]) - (7 if side_by_side else 4), f"{label}: grid leaves {len(rows[0]) - 1 - last} columns unused"


def key(*values):
    mux("send-keys", "-t", "test", *values)
    time.sleep(0.1)


def literal(value):
    mux("send-keys", "-t", "test", "-l", value)


def color(value, expected):
    screen = mux("capture-pane", "-t", "test", "-p", "-e").stdout
    foreground = None
    content = []
    for match in re.finditer(r"\x1b\[([\d;]*)m|([^\x1b]+)", screen):
        if match.group(1) is None:
            content.append(match.group(2) if foreground == expected else "\0" * len(match.group(2)))
            continue
        codes = [int(code or 0) for code in match.group(1).split(";")]
        index = 0
        while index < len(codes):
            code = codes[index]
            if code in (0, 39):
                foreground = None
            elif code in (38, 48) and index + 1 < len(codes):
                count = 3 if codes[index + 1] == 2 else 1
                if code == 38:
                    foreground = tuple(codes[index + 2:index + 2 + count])
                index += 1 + count
            index += 1
    assert value in "".join(content), f"{value!r} does not use {expected}\n{screen}"
    CAPTURES.append(f"=== {value}: color {expected} ===\n{screen}")


class Provider(http.server.BaseHTTPRequestHandler):
    def log_message(self, *values):
        pass

    def do_POST(self):
        REQUESTS.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        events = [
            {"type": "response.created"},
            {"type": "response.output_item.added", "output_index": 0, "item": {"type": "message"}},
            {"type": "response.content_part.added", "output_index": 0, "content_index": 0, "part": {"type": "output_text"}},
            {"type": "response.output_text.delta", "output_index": 0, "delta": "Context fixture reply."},
            {"type": "response.output_text.done", "output_index": 0},
            {"type": "response.content_part.done", "output_index": 0, "content_index": 0, "part": {"type": "output_text"}},
            {"type": "response.completed", "response": {"status": "completed", "usage": {"input_tokens": 42000, "output_tokens": 500, "input_tokens_details": {"cached_tokens": 40000}}}},
        ]
        for event in events:
            self.wfile.write(("data: " + json.dumps(event) + "\n\n").encode())
        self.wfile.flush()


server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Provider)
threading.Thread(target=server.serve_forever, daemon=True).start()
try:
    with tempfile.TemporaryDirectory(prefix="yuke-context-tui-") as directory:
        root = Path(directory).resolve()
        config = root / "config/yuke"
        (config / "plugins").mkdir(parents=True)
        workspace = root / "workspace"
        workspace.mkdir()
        (workspace / "AGENTS.md").write_text("Use fixture instructions.\n")
        skill = workspace / ".agents/skills/demo"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: demo\ndescription: A fixture skill\n---\nPrivate skill body\n")
        (config / "plugins/context-data.py").symlink_to(PROFILE / "plugins/context-data.py")
        if args.full_profile:
            for child in (PROFILE / "plugins").iterdir():
                if not (config / "plugins" / child.name).exists():
                    (config / "plugins" / child.name).symlink_to(child)
            (config / "tools").symlink_to(PROFILE / "tools", target_is_directory=True)
        load = f'import {json.dumps(str(PROFILE / "index.js"))};\n' if args.full_profile else (
            f'import {{ solarizedTheme }} from {json.dumps(str(PROFILE / "plugins/solarized-theme.js"))};\nplugins.use(solarizedTheme);\n')
        summary = '<available_skills>\n  <skill>\n    <name>demo</name>\n    <description>A fixture skill</description>\n    <location>/fixture/demo/SKILL.md</location>\n  </skill>\n</available_skills>'
        (config / "index.js").write_text(
            'import { plugins, defineConfig } from "yuke";\n'
            'import { currentPane } from "yuke:session";\n'
            f'import {{ contextDashboard }} from {json.dumps(str(PROFILE / "plugins/context-dashboard.js"))};\n'
            f'defineConfig({{ colors: {json.dumps(args.colors)} }});\n' + load +
            ('' if args.full_profile else 'let handle = plugins.use(contextDashboard);\n') +
            'plugins.use({ name: "context-probe", apply(ctx) {\n'
            '  ctx.hook("prompt.build", p => ({ replace: { sections: [\n'
            '    { key: "base", text: "b".repeat(2000) }, { key: "instructions", text: "i".repeat(10000) },\n'
            f'    {{ key: "skills", text: {json.dumps(summary)}.padEnd(10000, "s") }},\n'
            '  ] }}));\n'
            '  ctx.tools.define({ name: "context_fixture_tool", description: "Fixture definition size. ".repeat(300), parameters: { type: "object", properties: { text: { type: "string" } } }, execute: () => "not called" });\n'
            '  ctx.inject(["tui"], c => {\n'
            '    c.tui.keymap.add({ f6: "context:show", f9: () => currentPane()?.composer.input.setText("Keep this unsent draft") });\n' +
            ('' if args.full_profile else
             '    c.tui.command.add("context-test:unload", { aboveModal: true, run: async () => { await handle.dispose(); c.interaction.notify("Context plugin unloaded"); } });\n'
             '    c.tui.command.add("context-test:load", { run: () => { handle = plugins.use(contextDashboard); c.interaction.notify("Context plugin reloaded"); } });\n'
             '    c.tui.keymap.add({ f7: "context-test:unload", f8: "context-test:load" });\n') +
            '  });\n'
            '}});\n'
        )
        (config / "providers.json").write_text(json.dumps({"providers": [{
            "id": "probe", "base_url": f"http://127.0.0.1:{server.server_port}/v1",
            "endpoints": [{"protocol": "openai_responses"}], "models": [{"id": "model", "upstream_id": "model",
            "flags": {"supports_tools": True}, "limits": {"context_window": 128000, "max_output_tokens": 4096}}],
        }]}))
        (config / "providers.json").chmod(0o600)
        environment = {"HOME": str(root), "PATH": os.environ["PATH"], "SHELL": "/bin/bash", "TERM": "xterm-256color", "YUKE_APPNAME": "yuke"}
        for name in ("CONFIG", "DATA", "STATE", "CACHE"):
            environment["XDG_" + name + "_HOME"] = str(root / name.lower())
        result = subprocess.run([YUKE, "-p", "Context fixture", "--json", "--model", "probe/model"], env=environment, cwd=workspace, capture_output=True, text=True, timeout=30, check=True)
        session_id = next(json.loads(line)["session_id"] for line in result.stdout.splitlines() if '"session_id"' in line)
        run = root / "run.sh"
        import shlex
        run.write_text("#!/bin/sh\ncd " + shlex.quote(str(workspace)) + "\nexec env -i " +
                       " ".join(shlex.quote(key + "=" + value) for key, value in environment.items()) + " " +
                       shlex.join([YUKE, "resume", session_id]) + "\n")
        run.chmod(0o700)
        mux("new-session", "-d", "-x", "120", "-y", "44", "-s", "test", str(run))
        expect("saved chat", "Context fixture reply.")
        literal("\x1b]11;rgb:" + ("ffff/ffff/ffff" if args.background == "light" else "0000/0000/0000") + "\x1b\\")
        key("F9", "F6")
        overview = expect("overview", "Occupied context", "Tools / request overhead", "Skill catalog", "Chat + tool results + reasoning", "Each square", "■", "□", "▧", "4 UTF-8 bytes", absent=("NaN", "Infinity", "Private skill body"))
        grid_fills_width("wide overview", overview, side_by_side=True)
        key("v")
        expect("prompt grid zoom", "Each square", "saved prompt budget")
        key("v")
        expect("window grid restored", "Each square", "of the window")
        color("Tools / request overhead", COLORS["tools"])
        color("System + plugin instructions", COLORS["system"])
        color("Skill catalog", COLORS["skills"])
        color("Chat + tool results + reasoning", COLORS["chat"])
        key("2")
        expect("details", "Request budget", "Auto-compaction threshold", "111,616", "16,384", "40,000", "Saved prompt sections", "Instruction sources", "demo")
        key("3")
        expect("skill costs", "Per-skill summary cost", "demo", "% ctx", "Catalog header / separators", "tok", "B", absent=("Private skill body",))
        key("4")
        expect("tool costs", "Per-tool definition cost", "context_fixture_tool", "Description / schema bytes", "% ctx", "tok")
        key("1", "r")
        expect("refresh", "Context breakdown", absent=("Reading context",))
        assert len(REQUESTS) == 1, "Opening or refreshing context called the model"
        with sqlite3.connect(root / "data/yuke/yuke.db") as db:
            db.execute("UPDATE session_prompts SET generation=0 WHERE session_id=?", (bytes.fromhex(session_id),))
        key("r")
        expect("stale keeps prompt split", "Skill catalog", "System + plugin instructions", "AGENTS.md instructions", "Unknown", "Reload changed the next prompt", absent=("Context (split unavailable)",))
        color("Skill catalog", COLORS["skills"])
        assert len(REQUESTS) == 1, "Stale inspection called the model"
        key("Escape")
        expect("draft preserved", "Keep this unsent draft", absent=("Context breakdown",))
        key("F6")
        expect("reopen", "Context breakdown")
        if not args.full_profile:
            key("F7")
            expect("unload closes overlay", "Context plugin unloaded", "Keep this unsent draft", absent=("Context breakdown",))
            key("F6")
            expect("built-in restored", "last turn", "cache", absent=("Context breakdown",))
            key("Escape")
            expect("built-in closed", "Keep this unsent draft", absent=("last turn",))
            key("F8")
            expect("plugin reload", "Context plugin reloaded")
            key("F6")
            expect("reload restores dashboard", "Context breakdown")
        mux("resize-window", "-t", "test", "-x", "60", "-y", "24")
        narrow = expect("narrow grid", "Each square")
        grid_fills_width("narrow overview", narrow)
        key("NPage")
        expect("narrow footer", "Cached input still occupies context", absent=("NaN", "Infinity"))
        key("PPage")
        expect("page up restores grid", "Context grid", "Each square")
        key("2", "End")
        expect("narrow details", "demo", "summaries, not bodies")
        key("q")
        expect("narrow close", "Keep this unsent draft", absent=("Saved prompt sections",))
        mux("resize-window", "-t", "test", "-x", "120", "-y", "44")
        helper_link = config / "plugins/context-data.py"
        helper_link.unlink()
        key("F6")
        expect("reader failure", "Cannot read context", "Press r to retry")
        helper_link.symlink_to(PROFILE / "plugins/context-data.py")
        key("r")
        overview = expect("reader retry", "Context breakdown", absent=("Cannot read context",))
        row = next(i for i, line in enumerate(overview.splitlines()) if "2 Details" in line)
        column = overview.splitlines()[row].index("2 Details")
        literal(f"\x1b[<0;{column + 1};{row + 1}M")
        expect("mouse details", "Request budget", "Known API cost")
        key("Escape")
        key("C-q")
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline and mux("has-session", "-t", "test", check=False).returncode == 0:
            time.sleep(0.05)
        assert mux("has-session", "-t", "test", check=False).returncode != 0
        run.write_text(run.read_text().replace(shlex.join([YUKE, "resume", session_id]), shlex.quote(YUKE)))
        mux("new-session", "-d", "-x", "120", "-y", "44", "-s", "test", str(run))
        time.sleep(0.4)
        key("F6")
        expect("fresh draft", "Context · new chat", "No saved request yet", absent=("NaN", "Infinity"))
        key("2")
        expect("fresh draft details", "No saved prompt")
        key("Escape", "C-q")
        print("Context TUI passed", args.colors, args.background, "full-profile" if args.full_profile else "focused")
finally:
    mux("kill-server", check=False)
    server.shutdown()
    server.server_close()
    artifact = Path(tempfile.gettempdir()) / ("yuke-context-captures-" + uuid.uuid4().hex[:8] + ".txt")
    artifact.write_text("\n".join(CAPTURES))
    print("Captures:", artifact)
