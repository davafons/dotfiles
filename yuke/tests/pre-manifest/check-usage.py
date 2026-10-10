#!/usr/bin/env python3
"""Verify all /usage tabs and controls in a detached, isolated Yuke TUI."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import tempfile
import time
import uuid

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--colors", choices=["truecolor", "256"], default="truecolor")
parser.add_argument("--background", choices=["dark", "light"], default="dark")
ARGS = parser.parse_args()
PALETTES = {
    ("truecolor", "dark"): dict(title=(70, 149, 247), number=(65, 199, 185), reasoning=(183, 162, 232),
                                good=(117, 185, 56), cost=(219, 179, 45), danger=(255, 102, 92), heat=(255, 227, 172)),
    ("truecolor", "light"): dict(title=(0, 101, 153), number=(0, 111, 102), reasoning=(114, 75, 158),
                                 good=(59, 107, 20), cost=(118, 92, 0), danger=(181, 43, 40), heat=(89, 73, 11)),
    ("256", "dark"): dict(title=(75,), number=(80,), reasoning=(183,), good=(113,), cost=(179,), danger=(209,), heat=(223,)),
    ("256", "light"): dict(title=(24,), number=(23,), reasoning=(60,), good=(22,), cost=(58,), danger=(124,), heat=(58,)),
}
COLORS = PALETTES[(ARGS.colors, ARGS.background)]
PROFILE = Path(__file__).resolve().parents[1]
TMUX = shutil.which("tmux")
YUKE = shutil.which("yuke")
assert TMUX and YUKE, "tmux and yuke are required"
SOCKET = "yuke-usage-" + uuid.uuid4().hex[:10]
CAPTURES = []


def tmux(*args, check=True):
    return subprocess.run([TMUX, "-L", SOCKET, *args], check=check, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def screen():
    return tmux("capture-pane", "-t", "test", "-p").stdout


def expect(label, *words, absent=()):
    deadline = time.monotonic() + 10
    current = ""
    while time.monotonic() < deadline:
        current = screen()
        if all(word in current for word in words) and all(word not in current for word in absent):
            CAPTURES.append(f"=== {label} ===\n{current}")
            return current
        time.sleep(0.05)
    CAPTURES.append(f"=== FAILED {label} ===\n{current}")
    raise AssertionError(f"{label}: expected {words}, absent {absent}\n{current}")


def expect_color(label, value, color):
    styled = tmux("capture-pane", "-t", "test", "-p", "-e").stdout
    foreground = None
    colored_text = []
    for token in re.finditer(r"\x1b\[([\d;]*)m|([^\x1b]+)", styled):
        if token.group(1) is None:
            content = token.group(2)
            colored_text.append(content if foreground == color else "\0" * len(content))
            continue
        codes = [int(code or 0) for code in token.group(1).split(";")]
        index = 0
        while index < len(codes):
            code = codes[index]
            if code in (0, 39):
                foreground = None
            elif code in (38, 48) and index + 1 < len(codes):
                mode = codes[index + 1]
                count = 3 if mode == 2 else 1
                if code == 38:
                    foreground = tuple(codes[index + 2:index + 2 + count])
                index += 1 + count
            index += 1
    assert value in "".join(colored_text), f"{label}: {value!r} was not rendered in {color}\n{styled}"
    CAPTURES.append(f"=== {label} ANSI colors ===\n{styled}")


def key(*keys):
    tmux("send-keys", "-t", "test", *keys)
    time.sleep(0.1)


def literal(value):
    tmux("send-keys", "-t", "test", "-l", value)


def command(value):
    literal(value)
    key("Enter")


def mouse(column, row, button=0):
    literal(f"\x1b[<{button};{column};{row}M")
    if button == 0:
        literal(f"\x1b[<{button};{column};{row}m")
    time.sleep(0.1)


def seed(database, workspace, other):
    db = sqlite3.connect(database)
    now = datetime.now().astimezone()
    timestamp = int(now.timestamp() * 1000)
    root_id = bytes.fromhex("01" * 16)
    child_id = bytes.fromhex("02" * 16)
    other_id = bytes.fromhex("03" * 16)
    for sid, root, kind, title in [(root_id, workspace, "root", "Usage fixture main chat"),
                                   (child_id, workspace, "child", "Usage fixture child"),
                                   (other_id, other, "root", "Other workspace chat")]:
        db.execute("""INSERT INTO sessions (id, root, origin, model, reasoning, config_rev, title,
            name, parent_id, parent_message_id, parent_part_id, created_at_ms, updated_at_ms)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""", (sid, root, kind, "probe/model", "high", 0, title,
                "general" if kind == "child" else None, root_id if kind == "child" else None,
                1 if kind == "child" else None, 0 if kind == "child" else None, timestamp - 60000, timestamp))
        db.execute("INSERT INTO session_configs (session_id,config_rev,model,reasoning) VALUES (?,?,?,?)", (sid, 0, "probe/model", "high"))
    db.execute("INSERT INTO session_skills VALUES (?,?,?,?,?,?)", (root_id, "demo", "A fixture skill", "workspace", workspace + "/skills/demo/SKILL.md", workspace + "/skills/demo/SKILL.md"))
    for index in range(260):
        db.execute("""INSERT INTO sessions (id,root,origin,model,reasoning,config_rev,title,created_at_ms,updated_at_ms)
                      VALUES (?,?,?,?,?,?,?,?,?)""", (uuid.uuid4().bytes, other, "root", "probe/model", "medium", 0, "Older chat " + str(index), timestamp - 120000, timestamp - 120000))
    for sid, tokens, cost, model in [(root_id, (1200000, 50000, 10000, 1000000, 0), (2.5, 20.0), "probe/model"),
                                     (child_id, (100000, 50000, 20000, 80000, 20000), None, "second/child-model"),
                                     (other_id, (180000, 20000, 10000, 100000, 0), (0.5, 2.0), "probe/model")]:
        parts = [dict(type="text", id=0, text="Do not expose transcript contents")]
        if sid == root_id:
            for index, (name, arguments, state) in enumerate([
                ("read", {"path": "skills/demo/SKILL.md"}, "completed"),
                ("exec", {"command": "false"}, "error"),
            ], 1):
                parts.append(dict(type="tool", id=index, name=name, call_id=str(index), arguments=json.dumps(arguments),
                                  state=dict(type=state, duration_ms=100, output="PRIVATE TOOL OUTPUT")))
        message = dict(type="assistant", id=1, run_id=1, config_rev=0, content=parts, finish="stop",
                       tokens=dict(zip(("input", "output", "reasoning", "cache_read", "cache_write"), tokens)),
                       provenance=dict(model=model, protocol="openai_responses"),
                       time=dict(created_at_ms=timestamp - 5000, completed_at_ms=timestamp))
        if cost:
            message["cost"] = dict(total=cost[0], without_cache=cost[1])
        db.execute("INSERT INTO events VALUES (?,?,?,?,?,?)", (sid, 1, uuid.uuid4().bytes, timestamp, "message.committed", json.dumps(message)))
        db.execute("""UPDATE sessions SET usage_input_total=?,usage_output_total=?,usage_reasoning_total=?,
                      usage_cache_read_total=?,usage_cache_write_total=?,cost_total=?,cost_without_cache_total=?,
                      unpriced_count=? WHERE id=?""", (*tokens, cost[0] if cost else 0, cost[1] if cost else 0, int(cost is None), sid))
        run = dict(session_id=sid.hex(), seq=2, run_id=1, kind="turn", timing=dict(started_at_ms=timestamp - 5000, ended_at_ms=timestamp), outcome=dict(type="turn", finish="stop", rounds=1))
        db.execute("INSERT INTO events VALUES (?,?,?,?,?,?)", (sid, 2, uuid.uuid4().bytes, timestamp, "run.done", json.dumps(run)))
    db.commit()
    db.close()


try:
    with tempfile.TemporaryDirectory(prefix="yuke-usage-tui-") as directory:
        root = Path(directory).resolve()
        config = root / "config" / "yuke"
        (config / "plugins").mkdir(parents=True)
        (config / "plugins" / "usage-data.py").symlink_to(PROFILE / "plugins" / "usage-data.py")
        workspace = root / "workspace"
        workspace.mkdir()
        other = root / "other"
        other.mkdir()
        (config / "index.js").write_text(
            'import { plugins, defineConfig } from "yuke";\n'
            f'defineConfig({{ colors: {json.dumps(ARGS.colors)} }});\n'
            'import { Session } from "yuke:session";\n'
            f'import {{ usage }} from {json.dumps(str(PROFILE / "plugins" / "usage.js"))};\n'
            f'import {{ solarizedTheme }} from {json.dumps(str(PROFILE / "plugins" / "solarized-theme.js"))};\n'
            'plugins.use(solarizedTheme);\n'
            'plugins.use({ name: "usage-probe", apply(ctx) {\n'
            '  ctx.advise(Session.prototype, "open", "around", (_next, id) => {\n'
            '    ctx.interaction.notify("Resume requested: " + id); return false;\n'
            '  });\n'
            '}});\n'
            'plugins.use(usage);\n'
        )
        env = {f"XDG_{name}_HOME": str(root / name.lower()) for name in ["CONFIG", "DATA", "STATE", "CACHE"]}
        run = root / "run.sh"
        run.write_text("#!/bin/sh\n" + "\n".join(f"export {name}={json.dumps(value)}" for name, value in env.items()) +
                       "\nunset HERDR_ENV HERDR_PANE_ID HERDR_SOCKET_PATH YUKE_APPNAME\nexport TERM=xterm-256color COLORTERM=truecolor\n" +
                       f"cd {json.dumps(str(workspace))}\nexec {json.dumps(YUKE)}\n")
        run.chmod(0o700)
        tmux("new-session", "-d", "-x", "160", "-y", "50", "-s", "test", str(run))
        database = root / "data" / "yuke" / "yuke.db"
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if database.exists():
                try:
                    db = sqlite3.connect(database)
                    ready = db.execute("SELECT count(*) FROM sessions").fetchone() is not None
                    db.close()
                    if ready:
                        break
                except sqlite3.OperationalError:
                    pass
            time.sleep(0.05)
        else:
            raise AssertionError("Isolated Yuke did not initialize its database\n" + screen())

        background = "ffff/ffff/ffff" if ARGS.background == "light" else "0000/0000/0000"
        literal("\x1b]11;rgb:" + background + "\x1b\\")
        time.sleep(0.1)
        command("/usage")
        expect("empty overview", "Global · all workspaces", "No recorded model activity yet.", "n/a")
        key("2")
        expect("empty consumption percentages", "Token breakdown", "$0.00 (n/a)", "0 (n/a)", absent=("NaN", "Infinity"))
        key("Escape")
        expect("escape restores chat", absent=("Token activity",))
        seed(database, str(workspace), str(other))

        command("/usage")
        expect("global overview", "1.6M", "Lifetime tokens", "Peak daily tokens", "Token activity", "Activity insights", "Most used tools and skills", "Statistics as of")
        styled = tmux("capture-pane", "-t", "test", "-p", "-e").stdout
        expect_color("high-activity heatmap", "▪", COLORS["heat"])
        CAPTURES.append("=== heatmap ANSI colors ===\n" + styled)
        expect_color("section headings", "Token activity", COLORS["title"])
        expect_color("token metrics", "1.6M", COLORS["number"])
        expect_color("reasoning metric", "high (100%)", COLORS["reasoning"])
        expect_color("cache savings percentage", "$19.00 (86.4%)", COLORS["good"])
        expect_color("cache hit percentage", "79.7%", COLORS["good"])
        expect_color("known cost", "$3.00 + unpriced", COLORS["cost"])
        key("2")
        expect("usage providers and models", "Token breakdown", "1,600,000", "Usage by provider", "second", "Usage by model", "second/child-model", "Replies with unknown prices")
        expect("consumption shares", "1,480,000 (92.5%)", "120,000 (7.5%)", "40,000 (33.3%)",
               "1,180,000 (79.7%)", "20,000 (1.4%)", "280,000 (18.9%)", "$3.00 (13.6%)", "$19.00 (86.4%)",
               "Cache writes (% of input)", "Uncached input (% of input)", "no-cache estimate for priced replies")
        expect("weighted provider and model cache shares", "1.1M (79.7%)", "80K (80.0%)")
        key("End")
        expect("daily usage", "Daily usage", "1.2M (79.7%)", "1 reply has unknown prices", absent=("PRIVATE",))
        expect_color("partial data warning", "1 reply has unknown prices", COLORS["cost"])
        key("g")
        key("End")
        expect("weekly usage", "Weekly usage · weeks start Monday", "1.2M (79.7%)")
        key("g")
        key("End")
        expect("monthly usage", "Monthly usage", "1.2M (79.7%)")
        key("3")
        expect("messages", "Message activity", "Assistant replies", "Reply finish reasons", "Run outcomes", "Reasoning effort by reply")
        key("4")
        expect("plugins and tools", "Loaded plugins", "usage-probe", "historical plugin run counts", "Tool activity", "Canceled", "exec", "read")
        expect_color("loaded plugin state", "● loaded", COLORS["good"])
        expect_color("tool names", "exec", COLORS["number"])
        expect_color("failed tool count", "1", COLORS["danger"])
        key("5")
        expect("skills", "Skill activity", "$demo", "Invocations", "File reads")
        expect_color("skill names", "$demo", COLORS["reasoning"])
        key("6")
        expect("chats", "Chats · newest first", "Usage fixture", "[child]", "Other workspace chat")
        expect_color("chat child badge", "[child]", COLORS["reasoning"])
        expect_color("chat model", "probe/model", COLORS["reasoning"])
        expect_color("chat tokens", "1.3M tokens", COLORS["number"])
        key("/")
        expect("chat search dialog", "Filter chats")
        literal("main chat")
        key("Enter")
        expect("filtered chat", "Search: main chat", "Usage fixture main chat", absent=("Other workspace chat", "Usage fixture child"))
        key("Enter")
        expect("resume selected chat", "Resume requested: " + "01" * 16, absent=("Chats · newest first",))

        command("/usage current")
        expect("workspace scope", "Workspace · workspace", "1.4M", "1 chat · 1 child session", "83.1%", "$17.50 (87.5%)")
        key("s")
        expect("scope switches globally", "Global · all workspaces", "1.6M")
        key("Tab")
        expect("tab navigation", "Token breakdown")
        key("BTab")
        expect("reverse tab navigation", "Token activity")
        mouse(53, 2)
        expect("mouse selects skills tab", "Skill activity", "$demo")
        mouse(2, 2)
        expect("mouse selects overview tab", "Token activity")
        mouse(2, 4)
        expect("mouse changes period", "g Weekly")
        mouse(15, 4)
        expect("mouse changes scope", "Workspace · workspace", "1.4M")
        mouse(20, 20, button=65)
        expect("mouse wheel scrolls", "Token activity")
        key("q")
        expect("q restores chat", absent=("Token activity",))

        command("/usage")
        tmux("resize-window", "-t", "test", "-x", "50", "-y", "24")
        expect("narrow layout", "Lifetime tokens", "Recent", "weeks (resize for 12 months)")
        key("j", "j", "j", "j", "j", "j", "j", "j", "j", "j", "j", "j", "j", "j", "j", "j", "j", "j")
        expect("narrow scrolling", "Activity insights")
        key("2")
        expect("narrow consumption shares", "Token breakdown", "1,180,000 (79.7%)", "20,000 (1.4%)", "$19.00 (86.4%)")
        key("6")
        expect("narrow chats", "Chats · newest first", "Usage fixture")
        key("j")
        expect("chat selection moves", "› Usage fixture")
        key("C-c")
        expect("ctrl-c closes dashboard", absent=("Chats · newest first",))
        tmux("resize-window", "-t", "test", "-x", "160", "-y", "50")

        command("/usage")
        expect("refresh initial value", "1.6M")
        db = sqlite3.connect(database)
        db.execute("UPDATE sessions SET usage_input_total=usage_input_total+1000000 WHERE id=?", (bytes.fromhex("01" * 16),))
        db.commit()
        db.close()
        mouse(24, 4)
        expect("mouse refresh reads new totals", "2.6M", "Breakdowns cover retained events.")
        key("Escape")

        reader_link = config / "plugins" / "usage-data.py"
        reader_link.unlink()
        command("/usage")
        expect("reader error is visible", "Cannot load usage", "Press r to retry")
        reader_link.symlink_to(PROFILE / "plugins" / "usage-data.py")
        key("r")
        expect("retry recovers", "2.6M", "Token activity")
        key("Escape")
        assert not list((root / "cache" / "yuke" / "usage").glob("*.json")), "Private snapshots were not removed"
        log = root / "state" / "yuke" / "yuke.log"
        if log.exists():
            text = log.read_text()
            assert "TypeError" not in text and "ReferenceError" not in text, text[-4000:]
finally:
    tmux("kill-server", check=False)
    with tempfile.NamedTemporaryFile(prefix="yuke-usage-tui-", suffix=".txt", mode="w", delete=False) as artifact:
        artifact.write("\n".join(CAPTURES))
        print("Saved usage TUI transcript:", artifact.name)

print(f"Usage TUI tmux check passed ({ARGS.colors}/{ARGS.background})")
