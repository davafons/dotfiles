#!/usr/bin/env python3
"""Check panel movement and prompt/history focus through a Ghostty-format tmux client."""
import fcntl
import json
import os
import pathlib
import pty
import shutil
import struct
import subprocess
import tempfile
import termios
import time
import uuid

TMUX = shutil.which("tmux")
YUKE = shutil.which("yuke")
assert TMUX, "tmux is required"
assert YUKE, "yuke is required"
plugin = pathlib.Path(__file__).resolve().parents[1] / "plugins" / "vim-improved.js"
tmux_config = pathlib.Path.home() / ".config" / "tmux" / "tmux.conf"
socket = "yuke-navigation-" + uuid.uuid4().hex[:10]
transcript = []
client = None
master = None


def tmux(*args, check=True):
    return subprocess.run(
        [TMUX, "-L", socket, *args], check=check, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )


def capture(label):
    screen = tmux("capture-pane", "-t", "test", "-p", "-S", "-28").stdout
    transcript.append(f"=== {label} ===\n{screen}")
    return screen


def wait_screen(label, text, timeout=5):
    deadline = time.monotonic() + timeout
    screen = ""
    while time.monotonic() < deadline:
        screen = capture(label)
        if text in screen:
            return screen
        transcript.pop()
        time.sleep(0.05)
    raise AssertionError(f"timed out at {label}\n{screen}")


def send(data):
    assert master is not None
    os.write(master, data)


try:
    with tempfile.TemporaryDirectory(prefix="yuke-navigation-") as directory:
        root = pathlib.Path(directory)
        profile = root / "config" / "yuke"
        profile.mkdir(parents=True)
        (profile / "index.js").write_text(
            'import { plugins } from "yuke";\n'
            f'import {{ vimImproved }} from {json.dumps(str(plugin))};\n'
            'plugins.use(vimImproved);\n'
            'plugins.use({ name: "navigation-check", apply(ctx) {\n'
            '  ctx.inject(["tui"], c => {\n'
            '    const left = c.tui.root.active;\n'
            '    c.tui.command.perform("window:split-right");\n'
            '    const upper = c.tui.root.active;\n'
            '    c.tui.command.perform("window:split-down");\n'
            '    const lower = c.tui.root.active;\n'
            '    c.tui.status.add({ side: "left", order: -100, render: () => {\n'
            '      const active = c.tui.root.active;\n'
            '      const name = active === left ? "LEFT" : active === upper ? "UPPER" : active === lower ? "LOWER" : "UNKNOWN";\n'
            '      return name + " " + String(active?.focus || "").toUpperCase();\n'
            '    }});\n'
            '  });\n'
            '}});\n'
        )
        run = root / "run.sh"
        run.write_text(
            "#!/bin/sh\n"
            f"export XDG_CONFIG_HOME={json.dumps(str(root / 'config'))}\n"
            f"export XDG_DATA_HOME={json.dumps(str(root / 'data'))}\n"
            f"export XDG_STATE_HOME={json.dumps(str(root / 'state'))}\n"
            f"export XDG_CACHE_HOME={json.dumps(str(root / 'cache'))}\n"
            "export TERM=tmux-256color\n"
            f"exec {json.dumps(YUKE)}\n"
        )
        run.chmod(0o700)
        subprocess.run(
            [TMUX, "-L", socket, "-f", str(tmux_config), "new-session", "-d", "-x", "100", "-y", "28", "-s", "test", str(run)],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 28, 100, 0, 0))
        env = os.environ.copy()
        env["TERM"] = "xterm-ghostty"
        client = subprocess.Popen(
            [TMUX, "-L", socket, "attach-session", "-t", "test"],
            stdin=slave, stdout=slave, stderr=slave, env=env,
        )
        os.close(slave)
        wait_screen("initial lower panel", "LOWER COMPOSER")

        # CSI-u Ctrl+K, as carried by Ghostty and tmux, moves to the panel above.
        send(b"\x1b[107;5u")
        wait_screen("Ctrl+K moves up", "UPPER COMPOSER")

        # Legacy Ctrl+J remains a newline while the prompt is in insert mode.
        send(b"\x0a")
        wait_screen("Ctrl+J stays in insert prompt", "UPPER COMPOSER")

        send(b"\x09")
        wait_screen("Tab focuses history", "UPPER TRANSCRIPT")
        send(b"\x0a")
        wait_screen("Ctrl+J moves down", "LOWER COMPOSER")

        send(b"\x1b[104;5u")
        wait_screen("Ctrl+H moves left", "LEFT COMPOSER")
        send(b"\x1b[108;5u")
        wait_screen("Ctrl+L moves right", "UPPER COMPOSER")

        send(b"\x09")
        wait_screen("Tab focuses history again", "UPPER TRANSCRIPT")
        send(b"\x09")
        wait_screen("Tab returns to prompt", "UPPER COMPOSER")
finally:
    tmux("kill-server", check=False)
    if client is not None:
        try:
            client.wait(timeout=2)
        except subprocess.TimeoutExpired:
            client.kill()
            client.wait()
    if master is not None:
        os.close(master)
    with tempfile.NamedTemporaryFile(prefix="yuke-navigation-", suffix=".txt", mode="w", delete=False) as artifact:
        artifact.write("\n".join(transcript))
        print("Saved panel navigation transcript:", artifact.name)

print("Panel and region navigation Ghostty-to-tmux check passed")
