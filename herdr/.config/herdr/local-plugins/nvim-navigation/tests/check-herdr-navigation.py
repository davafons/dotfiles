#!/usr/bin/env python3
"""Exercise real Herdr dispatch in a detached terminal, never user panes.

A raw-input executable named yuke proves key delivery without submitting
prompts, accessing models, or interpreting input as commands.
Requires Herdr, tmux, cc, and the linked local plugins.
"""

import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import uuid

SESSION = "agent-tests-navigation-" + uuid.uuid4().hex[:8]
TMUX_SOCKET = SESSION
HERDR = os.environ.get("HERDR_TEST_BINARY") or shutil.which("herdr")
TMUX = shutil.which("tmux")
CC = shutil.which("cc")
assert HERDR and TMUX and CC, "herdr, tmux, and cc are required"
ENV = dict(os.environ)
for key in ("HERDR_ENV", "HERDR_SOCKET_PATH", "HERDR_ACTIVE_PANE_ID", "HERDR_PANE_ID", "HERDR_WORKSPACE_ID", "HERDR_TAB_ID"):
    ENV.pop(key, None)
server = None
socket_path = None
captures = []


def execute(argv, check=True):
    return subprocess.run(argv, env=ENV, capture_output=True, text=True, timeout=15, check=check)


def herdr(*args, check=True):
    return execute([HERDR, "--session", SESSION, *args], check)


def tmux(*args, check=True):
    return execute([TMUX, "-L", TMUX_SOCKET, *args], check)


def api(method, params=None):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(5)
        connection.connect(str(socket_path))
        connection.sendall((json.dumps({"id": "navigation-test", "method": method, "params": params or {}}) + "\n").encode())
        with connection.makefile("rb") as replies:
            response = json.loads(replies.readline())
    assert "error" not in response, response
    return response["result"]


def wait(condition, label, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = condition()
        if result:
            return result
        time.sleep(0.05)
    raise AssertionError("Timed out: " + label)


def snapshot():
    return api("session.snapshot")["snapshot"]


def pane_text(pane_id):
    return herdr("pane", "read", pane_id, "--source", "recent-unwrapped", "--lines", "50").stdout


def send(data):
    tmux("send-keys", "-t", "test", "-H", *(f"{byte:02x}" for byte in data))


def capture(label, ansi=False):
    flags = ["-e"] if ansi else []
    result = tmux("capture-pane", "-t", "test", "-p", *flags).stdout
    captures.append(f"=== {label} ===\n{result}")
    return result


try:
    with tempfile.TemporaryDirectory(prefix="herdr-navigation-") as directory:
        root = Path(directory)
        # Keep test clients away from saved machines and live client preferences.
        ENV["XDG_STATE_HOME"] = str(root / "state")
        source = root / "fixture.c"
        source.write_text(r'''
#include <stdio.h>
#include <termios.h>
#include <unistd.h>
int main(void) {
    struct termios raw;
    if (tcgetattr(0, &raw) != 0) return 1;
    cfmakeraw(&raw);
    tcsetattr(0, TCSANOW, &raw);
    setbuf(stdout, NULL);
    puts("YUKE_KEY_FIXTURE_READY\r");
    unsigned char key;
    while (read(0, &key, 1) == 1) printf("HEX_%02x\r\n", key);
    return 0;
}
''')
        fixture = root / "yuke"
        execute([CC, str(source), "-o", str(fixture)])
        with (root / "server.log").open("w") as log:
            server = subprocess.Popen([HERDR, "--session", SESSION, "server"], env=ENV, stdout=log, stderr=log)
            status = wait(lambda: (text if "status: running" in (text := herdr("status", check=False).stdout) else None), "test server")
            socket_path = Path(re.search(r"socket:\s*(.+)", status).group(1).strip())
            created = api("workspace.create", {"cwd": str(root), "label": "shirabe", "focus": False})
            top = created["root_pane"]["pane_id"]
            bottom = api("pane.split", {"target_pane_id": top, "direction": "down", "cwd": str(root), "focus": False})["pane"]["pane_id"]
            api("pane.focus", {"pane_id": top})
            herdr("pane", "run", top, "exec " + shlex.quote(str(fixture)))
            wait(lambda: "YUKE_KEY_FIXTURE_READY" in pane_text(top), "raw-input fixture")
            info = api("pane.process_info", {"pane_id": top})["process_info"]
            assert info["foreground_processes"][0]["name"] == "yuke", info
            api("pane.report_agent", {"pane_id": top, "source": "test:navigation", "agent": "yuke", "state": "idle"})

            tmux_config = root / "tmux.conf"
            tmux_config.write_text('set -g default-terminal "tmux-256color"\nset -as terminal-features ",tmux-256color:RGB"\nset -g status off\n')
            launch = "exec " + shlex.quote(HERDR) + " --session " + shlex.quote(SESSION)
            tmux("-f", str(tmux_config), "new-session", "-d", "-s", "test", "-x", "160", "-y", "52", launch)
            wait(lambda: "YUKE_KEY_FIXTURE_READY" in capture("test TUI"), "test client")
            # Both legacy LF and enhanced Ctrl+J must reach the application,
            # even with a real Herdr pane below it.
            send(b"\x0a")
            wait(lambda: "HEX_0a" in pane_text(top), "legacy Ctrl+J passthrough")
            assert snapshot()["focused_pane_id"] == top
            for code, expected in [(106, "0a"), (107, "0b"), (104, "08"), (108, "0c")]:
                send(f"\x1b[{code};5u".encode())
                wait(lambda: "HEX_" + expected in pane_text(top), f"enhanced Ctrl+{chr(code)} passthrough")
                assert snapshot()["focused_pane_id"] == top
            capture("Ctrl+h/j/k/l delivered; Herdr focus unchanged")
            send(b"\x01j")
            wait(lambda: snapshot()["focused_pane_id"] == bottom, "prefix+j Herdr movement")
            send(b"\x01k")
            wait(lambda: snapshot()["focused_pane_id"] == top, "prefix+k Herdr movement")
            before = pane_text(top).count("HEX_0a")
            api("plugin.action.invoke", {"plugin_id": "david.nvim-navigation", "action_id": "down",
                "context": {"workspace_id": created["workspace"]["workspace_id"], "focused_pane_id": top}})
            wait(lambda: pane_text(top).count("HEX_0a") > before, "navigator action Yuke passthrough")
            assert snapshot()["focused_pane_id"] == top

            # Validate rendered layout and colors, not just TOML syntax.
            tokens = {"checkout": "auth-fix", "revision": "abcdwxyz", "vcs_status": "1 file · CONFLICT", "summary": "Yuke context"}
            api("pane.report_metadata", {"pane_id": top, "source": "test:sidebar", "tokens": tokens})
            def inline_header():
                text = capture("compact checkout header")
                return text if any("○" in line and "shirabe" in line and "auth-fix" in line and "abcd" in line for line in text.splitlines()) else None
            plain = wait(inline_header, "inline dot, project, checkout, and revision")
            assert "1 file" not in plain, "File count should not be displayed"
            assert "CONFLICT" not in plain, "VCS status row should not be displayed"
            styled = wait(lambda: (text if "Yuke context" in (text := capture("muted Yuke summary", ansi=True)) else None), "Yuke summary")
            assert "38;2;88;163;255" in styled, "Project blue missing"
            assert "38;2;68;184;168" in styled, "Checkout cyan missing"
            assert "38;2;180;158;232" in styled, "Revision purple missing"
            assert "jj /" not in styled
            yuke_line = next(line for line in styled.splitlines() if "Yuke context" in line)
            assert "38;2;88;110;117" in yuke_line, "Yuke summary dark gray missing"
            # A second, test-owned pane supplies the Codex title path for comparison.
            herdr("pane", "run", bottom, "printf '\\033]0;Codex context\\007'")
            api("pane.report_agent", {"pane_id": bottom, "source": "test:sidebar", "agent": "codex", "state": "idle"})
            def codex_sidebar_title():
                text = capture("muted Codex title", ansi=True)
                return text if any("Codex context" in line.split("│", 1)[0] for line in text.splitlines()) else None
            styled = wait(codex_sidebar_title, "Codex sidebar title")
            codex_line = next(line.split("│", 1)[0] for line in styled.splitlines() if "Codex context" in line.split("│", 1)[0])
            assert "38;2;88;110;117" in codex_line, "Codex title should match Yuke summary dark gray"
            api("pane.report_metadata", {"pane_id": top, "source": "test:sidebar", "tokens": {"checkout": "an-extra-long-checkout-name-for-truncation"}})
            wait(lambda: "…" in capture("long checkout ellipsis"), "checkout ellipsis")
            if os.environ.get("HERDR_TEST_TAB_STATUS_COLORS") == "1":
                for state, glyph, color in [("idle", "○", 32), ("working", "●", 33), ("blocked", "●", 91), ("idle", "○", 32)]:
                    api("pane.report_agent", {"pane_id": top, "source": "test:navigation", "agent": "yuke", "state": state})
                    api("plugin.action.invoke", {"plugin_id": "sidebar-numbers", "action_id": "sync"})
                    def colored_tab():
                        text = capture("tab status " + state, ansi=True)
                        line = text.splitlines()[0]
                        plain = re.sub(r"\x1b\[[0-9;]*m", "", line)
                        grouped_badge = re.search(r"\[[1-9]\d*(?:,[1-9]\d*)* " + glyph + r"\] ", plain)
                        colored_dot = re.search(r"\x1b\[(?:\d+;)*" + str(color) + "m" + glyph + r"(?:\x1b\[[0-9;]*m)*\]", line)
                        muted_brackets = all(re.search(r"\x1b\[(?:\d+;)*37m" + re.escape(bracket), line) for bracket in "[]")
                        return text if grouped_badge and colored_dot and muted_brackets else None
                    wait(colored_tab, state + " tab dot matches sidebar color")
finally:
    tmux("kill-server", check=False)
    if socket_path and sys.platform == "darwin":
        digest = hashlib.sha256(str(socket_path).encode()).hexdigest()[:12]
        label = "dev.herdr.workspaces." + digest
        execute(["launchctl", "bootout", f"gui/{os.getuid()}/{label}"], check=False)
        (Path.home() / "Library/LaunchAgents" / f"{label}.plist").unlink(missing_ok=True)
    if server is not None:
        herdr("session", "stop", SESSION, "--json", check=False)
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.terminate()
            server.wait(timeout=5)
        herdr("session", "delete", SESSION, "--json", check=False)
    with tempfile.NamedTemporaryFile(prefix="herdr-navigation-", suffix=".txt", mode="w", delete=False) as artifact:
        artifact.write("\n".join(captures))
        print("Saved detached-terminal checks:", artifact.name)

print("Herdr Ctrl+h/j/k/l routing and compact colored sidebar checks passed")
