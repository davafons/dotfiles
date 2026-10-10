#!/usr/bin/env python3
"""Test agent banks and zero shortcuts in a private Herdr/detached tmux session."""

import json
import os
from pathlib import Path
import re
import shlex
import shutil
import socket
import subprocess
import tempfile
import time
import uuid

SESSION = "agent-tests-shortcuts-" + uuid.uuid4().hex[:8]
HERDR = shutil.which("herdr")
TMUX = shutil.which("tmux")
assert HERDR and TMUX, "herdr and tmux are required"
ENV = {key: value for key, value in os.environ.items() if not key.startswith("HERDR_")}
server = None
address = None


def run(argv, check=True):
    return subprocess.run(argv, env=ENV, capture_output=True, text=True, timeout=15, check=check)


def herdr(*args, check=True):
    return run([HERDR, "--session", SESSION, *args], check)


def tmux(*args, check=True):
    return run([TMUX, "-L", SESSION, *args], check)


def api(method, params=None):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(5)
        connection.connect(str(address))
        connection.sendall((json.dumps({"id": "shortcuts-test", "method": method, "params": params or {}}) + "\n").encode())
        with connection.makefile("rb") as replies:
            response = json.loads(replies.readline())
    assert "error" not in response, response
    return response["result"]


def wait(condition, label, seconds=10):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        result = condition()
        if result:
            return result
        time.sleep(.05)
    raise AssertionError("Timed out: " + label)


def snapshot():
    return api("session.snapshot")["snapshot"]


def send(data):
    tmux("send-keys", "-t", "test", "-H", *(f"{byte:02x}" for byte in data))


try:
    with tempfile.TemporaryDirectory(prefix="hs-", dir="/tmp") as directory:
        root = Path(directory)
        for kind in ("CONFIG", "STATE", "CACHE", "DATA"):
            ENV[f"XDG_{kind}_HOME"] = str(root / kind.lower())
        plugin = Path(__file__).resolve().parents[1]
        config = root / "config/herdr"
        config.mkdir(parents=True)
        shutil.copyfile(plugin.parent.parent / "config.toml", config / "config.toml")
        linked = herdr("plugin", "link", str(plugin), "--enabled", check=False)
        assert linked.returncode == 0, linked.stdout + linked.stderr
        with (root / "server.log").open("w") as log:
            server = subprocess.Popen([HERDR, "--session", SESSION, "server"], env=ENV, stdout=log, stderr=log)
            status = wait(lambda: (r.stdout if "status: running" in (r := herdr("status", check=False)).stdout else None), "server")
            address = Path(re.search(r"socket:\s*(.+)", status).group(1).strip())
            for number in range(1, 21):
                pane = api("workspace.create", {"cwd": directory, "label": f"Agent Tests shortcuts {number}", "focus": False})["root_pane"]
                api("pane.report_agent", {"pane_id": pane["pane_id"], "source": "test:shortcuts", "agent": "codex", "state": "idle", "seq": 1})
            snap = snapshot()
            assert len(snap["agents"]) == 20
            workspace = snap["workspaces"][0]
            for _ in range(19):
                api("tab.create", {"workspace_id": workspace["workspace_id"], "cwd": directory, "focus": False})
            snap = snapshot()
            agent10 = snap["agents"][9]["pane_id"]
            workspace10 = snap["workspaces"][9]["workspace_id"]
            tab10 = [tab for tab in snap["tabs"] if tab["workspace_id"] == workspace["workspace_id"]][9]["tab_id"]
            tmux("new-session", "-d", "-s", "test", "-x", "180", "-y", "52", "exec " + shlex.quote(HERDR) + " --session " + shlex.quote(SESSION))
            wait(lambda: "Agent Tests shortcuts" in tmux("capture-pane", "-t", "test", "-p").stdout, "client ready")
            api("pane.focus", {"pane_id": snap["agents"][0]["pane_id"]})
            time.sleep(.3)
            send(b"\x010")
            wait(lambda: snapshot()["focused_tab_id"] == tab10, "Ctrl+a 0 -> tab 10")
            send(b"\x01\x1b[48;5u")
            wait(lambda: snapshot()["focused_pane_id"] == agent10, "Ctrl+a Ctrl+0 -> agent 10")
            api("workspace.focus", {"workspace_id": workspace["workspace_id"]})
            time.sleep(.2)
            send(b"\x01)")
            wait(lambda: snapshot()["focused_workspace_id"] == workspace10, "Ctrl+a Shift+0 -> workspace 10")
            print("PASS: tab, agent, and workspace 0 shortcuts")
            first = snap["agents"][0]["pane_id"]
            tabs = [tab for tab in snap["tabs"] if tab["workspace_id"] == workspace["workspace_id"]]
            banks = (
                ("tab", 3, "focused_tab_id", tabs, "tab_id", ("legacy", "CSI-u")),
                ("agent", 7, "focused_pane_id", snap["agents"], "pane_id", ("CSI-u",)),
                ("workspace", 4, "focused_workspace_id", snap["workspaces"], "workspace_id",
                 ("legacy", "CSI-u", "shifted CSI-u")),
            )
            for kind, modifier, focused_field, resources, id_field, protocols in banks:
                for protocol in protocols:
                    for number in range(11, 21):
                        # ESC ^ begins an ANSI privacy message, not an Alt key.
                        # Shift+Alt+6 needs CSI-u; Ctrl+Alt digits also need it.
                        if kind == "workspace" and protocol == "legacy" and number == 16:
                            continue
                        digit = str(number % 10)
                        symbol = ")!@#$%^&*("[number % 10] if kind == "workspace" else digit
                        api("pane.focus", {"pane_id": first})
                        time.sleep(.1)
                        if protocol == "legacy":
                            sequence = "\x1b" + symbol
                        else:
                            code = symbol if protocol == "shifted CSI-u" else digit
                            sequence = f"\x1b[{ord(code)};{modifier}u"
                        send(b"\x01" + sequence.encode())
                        target = resources[number - 1][id_field]
                        wait(lambda: snapshot()[focused_field] == target,
                             f"{kind} {number} ({protocol})")
                    count = 9 if kind == "workspace" and protocol == "legacy" else 10
                    print(f"PASS: {count} {kind} bank shortcuts ({protocol})")
            # Remove only fixtures, then verify missing positions preserve focus.
            api("tab.close", {"tab_id": tabs[19]["tab_id"]})
            api("workspace.close", {"workspace_id": snap["agents"][19]["workspace_id"]})
            for kind, modifier, *_ in banks:
                api("pane.focus", {"pane_id": first})
                time.sleep(.1)
                send(b"\x01" + f"\x1b[48;{modifier}u".encode())
                time.sleep(.5)
                assert snapshot()["focused_pane_id"] == first, f"Missing {kind} 20 focused another pane"
                print(f"PASS: missing {kind} 20 preserves focus")
except Exception:
    print(tmux("capture-pane", "-t", "test", "-p", check=False).stdout)
    if address is not None:
        print(herdr("plugin", "log", "list", "--plugin", "sidebar-numbers", check=False).stdout)
    raise
finally:
    tmux("kill-server", check=False)
    if server is not None:
        herdr("server", "stop", check=False)
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.terminate()
            server.wait(timeout=5)
