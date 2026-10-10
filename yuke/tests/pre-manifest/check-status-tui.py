#!/usr/bin/env python3
"""Drive real /status in detached tmux; quota fixtures run the production reader."""
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
parser.add_argument("--full-profile", action="store_true")
parser.add_argument("--colors", choices=["truecolor", "256"], default="truecolor")
parser.add_argument("--background", choices=["dark", "light"], default="dark")
args = parser.parse_args()
PROFILE = Path(__file__).resolve().parents[1]
YUKE = os.environ.get("YUKE_TEST_BINARY") or shutil.which("yuke")
TMUX = shutil.which("tmux")
assert YUKE and TMUX
SOCKET = "yuke-status-" + uuid.uuid4().hex[:10]
CAPTURES = []
REQUESTS = []
COLORS = {
    ("truecolor", "dark"): {"good": (117, 185, 56), "warn": (219, 179, 45), "danger": (255, 102, 92), "context": (65, 199, 185), "accent": (70, 149, 247), "plan": (183, 162, 232), "dim": (143, 167, 170)},
    ("truecolor", "light"): {"good": (59, 107, 20), "warn": (118, 92, 0), "danger": (181, 43, 40), "context": (0, 111, 102), "accent": (0, 101, 153), "plan": (114, 75, 158), "dim": (83, 99, 104)},
    ("256", "dark"): {"good": (113,), "warn": (179,), "danger": (209,), "context": (80,), "accent": (75,), "plan": (183,), "dim": (247,)},
    ("256", "light"): {"good": (22,), "warn": (58,), "danger": (124,), "context": (23,), "accent": (24,), "plan": (60,), "dim": (240,)},
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


def key(*values):
    for value in values:
        mux("send-keys", "-t", "test", value)
        time.sleep(0.15)


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
            {"type": "response.output_text.delta", "output_index": 0, "delta": "Status fixture reply."},
            {"type": "response.output_text.done", "output_index": 0},
            {"type": "response.content_part.done", "output_index": 0, "content_index": 0, "part": {"type": "output_text"}},
            {"type": "response.completed", "response": {"status": "completed", "usage": {"input_tokens": 42000, "output_tokens": 500,
                "input_tokens_details": {"cached_tokens": 40000}}}},
        ]
        for event in events:
            self.wfile.write(("data: " + json.dumps(event) + "\n\n").encode())
        self.wfile.flush()


server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Provider)
threading.Thread(target=server.serve_forever, daemon=True).start()
try:
    with tempfile.TemporaryDirectory(prefix="yuke-status-tui-") as directory:
        root = Path(directory)
        config = root / "config/yuke"
        (config / "plugins").mkdir(parents=True)
        workspace = root / "workspace"
        workspace.mkdir()
        (workspace / "AGENTS.md").write_text("Use fixture instructions.\n")
        state = root / "quota-state"
        state.write_text("weekly")
        calls = root / "quota-calls"
        helper = PROFILE / "plugins/status-data.py"
        (config / "plugins/status-data.py").write_text(
            'import importlib.util, pathlib, time\n'
            f'spec = importlib.util.spec_from_file_location("reader", {str(helper)!r})\n'
            'reader = importlib.util.module_from_spec(spec); spec.loader.exec_module(reader)\n'
            'def fixture(url, headers):\n'
            f'    with pathlib.Path({str(calls)!r}).open("a") as stream: stream.write(url + "\\n")\n'
            f'    mode = pathlib.Path({str(state)!r}).read_text()\n'
            '    if mode == "slow": time.sleep(6)\n'
            '    if mode == "error": raise reader.StatusError("Login expired (HTTP 401)")\n'
            '    if "openrouter" in url: return {"data": {"limit_remaining": 12.75, "free_model_daily_requests": {"remaining": 23}}}\n'
            '    weekly = {"used_percent": 0 if mode == "full" else 7, "limit_window_seconds": 604800, "reset_at": 1792327366}\n'
            '    five = {"used_percent": 82 if mode == "low" else 100, "limit_window_seconds": 18000, "reset_at": 1792327366}\n'
            '    return {"plan_type": "plus", "rate_limit": {"primary_window": five if mode in ("both", "low") else weekly,\n'
            '        "secondary_window": weekly if mode in ("both", "low") else None}, "credits": {"balance": "9915.4961790000", "unlimited": False}}\n'
            'reader.read_json = fixture\nreader.main()\n'
        )
        if args.full_profile:
            for child in (PROFILE / "plugins").iterdir():
                if not (config / "plugins" / child.name).exists():
                    (config / "plugins" / child.name).symlink_to(child)
            (config / "tools").symlink_to(PROFILE / "tools", target_is_directory=True)
        load = f'import {json.dumps(str(PROFILE / "index.js"))};\n' if args.full_profile else (f'import {{ solarizedTheme }} from {json.dumps(str(PROFILE / "plugins/solarized-theme.js"))};\n' + "plugins.use(solarizedTheme);\nlet handle = plugins.use(status);\n")
        (config / "index.js").write_text(
            'import { plugins, client, defineConfig } from "yuke";\n'
            'import { currentPane } from "yuke:session";\n'
            f'import {{ status }} from {json.dumps(str(PROFILE / "plugins/status.js"))};\n'
            f'defineConfig({{ colors: {json.dumps(args.colors)} }});\n' + load +
            'plugins.use({ name: "status-probe", apply(ctx) { ctx.inject(["tui"], c => {\n'
            '  const choose = async selector => { const catalog = await client.catalogList(null);\n'
            '    const model = catalog.type === "full" && catalog.models.find(m => m.selector === selector);\n'
            '    if (model) currentPane().session.setModel(model, "high"); else c.interaction.notify("Missing fixture model " + selector, "error"); };\n'
            '  c.tui.keymap.add({ f6: "status:show", f5: () => { void choose("openai-codex/status-fixture"); },\n'
            '    f8: () => { void choose("probe/model"); }, f3: () => { void choose("openrouter/status-fixture"); },\n'
            '    f9: () => currentPane().composer.input.setText("Keep this unsent draft") });\n' +
            ("" if args.full_profile else
             '  c.tui.command.add("status-test:unload", { aboveModal: true, run: async () => { await handle.dispose(); c.interaction.notify("Status plugin unloaded"); } });\n'
             '  c.tui.keymap.add({ f7: "status-test:unload", f4: () => { handle = plugins.use(status); c.interaction.notify("Status plugin reloaded"); } });\n') +
            '}); }});\n'
        )
        (config / "providers.json").write_text(json.dumps({"providers": [
            {"id": "probe", "base_url": f"http://127.0.0.1:{server.server_port}/v1", "endpoints": [{"protocol": "openai_responses"}],
             "models": [{"id": "model", "upstream_id": "model", "limits": {"context_window": 128000, "max_output_tokens": 4096}, "reasoning_levels": ["high"]}]},
            {"id": "openai-codex", "auth": {"oauth": {"access_token": "SECRET_TOKEN", "account_id": "SECRET_ACCOUNT", "expires_at_ms": 9000000000000}},
             "models": [{"id": "status-fixture", "upstream_id": "fixture", "limits": {"context_window": 128000, "max_output_tokens": 4096}, "reasoning_levels": ["high"]}]},
            {"id": "openrouter", "api_key": "SECRET_ROUTER", "models": [{"id": "status-fixture", "upstream_id": "fixture", "reasoning_levels": ["high"]}]},
        ]}))
        (config / "providers.json").chmod(0o600)
        environment = {"HOME": str(root), "PATH": os.environ["PATH"], "SHELL": "/bin/bash", "TERM": "xterm-256color", "YUKE_APPNAME": "yuke"}
        for name in ("CONFIG", "DATA", "STATE", "CACHE"):
            environment["XDG_" + name + "_HOME"] = str(root / name.lower())
        result = subprocess.run([YUKE, "-p", "Status fixture", "--json", "--model", "probe/model"], env=environment, cwd=workspace,
                                capture_output=True, text=True, timeout=30, check=True)
        session_id = next(json.loads(line)["session_id"] for line in result.stdout.splitlines() if '"session_id"' in line)
        run = root / "run.sh"
        run.write_text("#!/bin/sh\ncd " + shlex.quote(str(workspace)) + "\nexec env -i " +
                       " ".join(shlex.quote(key + "=" + value) for key, value in environment.items()) + " " + shlex.join([YUKE, "resume", session_id]) + "\n")
        run.chmod(0o700)
        mux("new-session", "-d", "-x", "120", "-y", "52", "-s", "test", str(run))
        expect("saved chat", "Status fixture reply.")
        mux("send-keys", "-t", "test", "-l", "\x1b]11;rgb:" + ("ffff/ffff/ffff" if args.background == "light" else "0000/0000/0000") + "\x1b\\")
        if not args.full_profile:
            mux("send-keys", "-t", "test", "-l", "/status")
            key("Enter")
        else:
            key("F6")
        expect("compact unsupported provider", "Account allowance", "42,006", "128,000", "42,500", "Account quota unavailable", "█", "░", absent=("NaN", "Infinity", "SECRET", "Authentication", "AGENTS.md", "Known API cost", "===="))
        color("67% free", COLORS["context"])
        color("d details", COLORS["accent"])
        assert "j/k" not in mux("capture-pane", "-t", "test", "-p").stdout, "Footer must omit j/k instructions"
        color("░", COLORS["dim"])
        key("d", "End")
        expect("details retains session counts", "42,000 input", "500 output", "40,000 tokens", "Max output", "Not reported by provider")
        color("42,000 input", COLORS["context"])
        color("40,000 tokens", COLORS["context"])
        color("unpriced replies", COLORS["warn"])
        key("Home", "d")
        expect("details hidden", "Account allowance", absent=("Known API cost", "Authentication"))
        key("Escape", "F5")
        time.sleep(0.3)
        key("F9", "F6")
        screen = expect("compact weekly-only shape", "Weekly limit", "93% left", "9915.50 credits", "plus", "█", "░", absent=("SECRET", "NaN", "Infinity", "Authentication", "AGENTS.md", "====", "5h limit not reported", "remaining-token count"))
        color("93% left", COLORS["good"])
        color("█", COLORS["good"])
        color("9915.50 credits", COLORS["context"])
        assert sum("│" in row for row in screen.splitlines()) < 25, "Default status is not compact"
        rows = screen.splitlines()
        for label in ("Resets ", "tokens used · estimated"):
            index = next(i for i, row in enumerate(rows) if label in row)
            assert not rows[index + 1].split("│")[1].strip(), "Missing space after " + label
        key("d", "End")
        expect("diagnostics available", "Details", "Tokens remaining", "Not reported by provider", "Build", "AGENTS.md")
        color("openai-codex/status-fixture", COLORS["plan"])
        color("oauth / ready", COLORS["good"])
        key("Home", "d")
        state.write_text("both")
        key("r")
        expect("exhausted five-hour allowance", "5h limit", "0% left", "Weekly limit", "93% left", absent=("5h limit not reported", "===="))
        color("0% left", COLORS["danger"])
        exhausted = mux("capture-pane", "-t", "test", "-p").stdout
        empty_bar = next(row for row in exhausted.splitlines() if "  0% left" in row)
        assert "░" in empty_bar and "█" not in empty_bar, "An exhausted allowance must have an empty bar"
        state.write_text("low")
        key("r")
        expect("low allowance", "18% left", "93% left")
        color("18% left", COLORS["warn"])
        state.write_text("full")
        key("r")
        full = expect("full allowance", "100% left", absent=("18% left",))
        full_bar = next(row for row in full.splitlines() if "100% left" in row)
        assert "█" in full_bar and "░" not in full_bar, "A full allowance must have a full bar"
        state.write_text("error")
        key("r")
        expect("failure clears old quota", "Login expired (HTTP 401)", absent=("93% left", "9915.50 credits"))
        state.write_text("weekly")
        key("r")
        expect("retry", "93% left", "9915.50 credits", absent=("Login expired",))
        key("Escape")
        expect("draft retained", "Keep this unsent draft", absent=("Account allowance",))
        key("F3")
        time.sleep(0.3)
        key("F6")
        expect("provider change selects OpenRouter", "OpenRouter", "$12.75", "23 left today", absent=("Weekly limit", "9915.50", "Key cap, not account balance"))
        key("Escape", "F5")
        time.sleep(0.3)
        key("F6")
        expect("Codex after switch", "93% left")
        mux("resize-window", "-t", "test", "-x", "58", "-y", "14")
        key("End")
        bottom = expect("narrow terminal scroll", "Context space", "estimated", absent=("NaN", "Infinity",))
        key("PPage")
        previous = mux("capture-pane", "-t", "test", "-p").stdout
        assert previous != bottom, "PageUp did not scroll"
        CAPTURES.append("=== PageUp ===\n" + previous)
        key("NPage")
        assert mux("capture-pane", "-t", "test", "-p").stdout == bottom, "PageDown did not restore the scroll position"
        mux("resize-window", "-t", "test", "-x", "120", "-y", "52")
        key("Home")
        expect("resize restored", "Account allowance", "93% left")
        if not args.full_profile:
            key("F7")
            expect("unloaded while open", "Status plugin unloaded", "Keep this unsent draft", absent=("Account allowance",))
            key("F4", "F6")
            expect("reloaded", "Account allowance", "93% left")
        key("Escape")
        state.write_text("slow")
        key("F6")
        expect("pending reader", "Reading allowance...")
        key("Escape")
        expect("close cancels read", "Keep this unsent draft", absent=("Account allowance",))
        state.write_text("weekly")
        key("F6")
        expect("reopen after cancellation", "Account allowance", "93% left")
        key("Escape", "C-n", "F6")
        expect("fresh draft", "New draft", "no request yet", "93% left", absent=("500 output", "SECRET"))
        assert len(REQUESTS) == 1, "Status sent a model request"
        assert all("SECRET" not in capture for capture in CAPTURES)
        query_log = calls.read_text().splitlines()
        assert query_log and all(url in ("https://chatgpt.com/backend-api/wham/usage", "https://openrouter.ai/api/v1/key") for url in query_log)
        print("PASS: compact card, solid bars, palette colors, details, quota data, drafts, resize, lifecycle; one loopback model call")
finally:
    mux("kill-server", check=False)
    server.shutdown()
    artifact = Path(tempfile.gettempdir()) / (SOCKET + ".txt")
    artifact.write_text("\n".join(CAPTURES))
    print("CAPTURES", artifact)
