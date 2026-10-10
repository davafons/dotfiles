#!/usr/bin/env python3
"""Check Ctrl+C in an isolated Yuke TUI inside tmux. Do not use desktop input."""
import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import time
import uuid

TMUX = shutil.which("tmux")
YUKE = shutil.which("yuke")
assert TMUX, "tmux is required"
assert YUKE, "yuke is required"
plugin = pathlib.Path(__file__).resolve().parents[1] / "plugins" / "ctrl-c.js"
session = "yuke-ctrl-c-" + uuid.uuid4().hex[:10]
transcript = []


def tmux(*args, check=True):
    return subprocess.run(
        [TMUX, *args], check=check, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )


def capture(target, label):
    screen = tmux("capture-pane", "-t", target, "-p", "-S", "-28").stdout
    transcript.append(f"=== {label} ===\n{screen}")
    return screen


def wait_screen(target, label, accept, timeout=5):
    deadline = time.monotonic() + timeout
    screen = ""
    while time.monotonic() < deadline:
        screen = capture(target, label)
        if accept(screen):
            return screen
        transcript.pop()
        time.sleep(0.05)
    raise AssertionError(f"timed out at {label}\n{screen}")


try:
    with tempfile.TemporaryDirectory(prefix="yuke-ctrl-c-") as directory:
        root = pathlib.Path(directory)
        profile = root / "config" / "yuke"
        profile.mkdir(parents=True)
        (profile / "index.js").write_text(
            'import { plugins } from "yuke";\n'
            'import { composerVim } from "yuke:plugins";\n'
            f'import {{ ctrlC }} from {json.dumps(str(plugin))};\n'
            'plugins.use(composerVim);\n'
            'plugins.use(ctrlC);\n'
        )
        run = root / "run.sh"
        run.write_text(
            "#!/bin/sh\n"
            f"export XDG_CONFIG_HOME={json.dumps(str(root / 'config'))}\n"
            f"export XDG_DATA_HOME={json.dumps(str(root / 'data'))}\n"
            f"export XDG_STATE_HOME={json.dumps(str(root / 'state'))}\n"
            f"export XDG_CACHE_HOME={json.dumps(str(root / 'cache'))}\n"
            "export TERM=xterm-256color\n"
            f"exec {json.dumps(YUKE)}\n"
        )
        run.chmod(0o700)
        tmux("new-session", "-d", "-x", "100", "-y", "28", "-s", session, str(run))
        target = tmux("list-panes", "-t", session, "-F", "#{pane_id}").stdout.strip()
        wait_screen(target, "initial normal", lambda s: "NORMAL" in s)

        tmux("send-keys", "-t", target, "i")
        tmux("send-keys", "-t", target, "-l", "insert draft")
        wait_screen(target, "insert content before Ctrl+C", lambda s: "insert draft" in s and "INSERT" in s)
        tmux("send-keys", "-t", target, "C-c")
        wait_screen(target, "insert content after Ctrl+C", lambda s: "insert draft" not in s and "NORMAL" in s)

        tmux("send-keys", "-t", target, "i")
        tmux("send-keys", "-t", target, "-l", "normal draft")
        tmux("send-keys", "-t", target, "Escape")
        wait_screen(target, "normal content before Ctrl+C", lambda s: "normal draft" in s and "NORMAL" in s)
        tmux("send-keys", "-t", target, "C-c")
        wait_screen(target, "normal content after Ctrl+C", lambda s: "normal draft" not in s and "NORMAL" in s)

        tmux("send-keys", "-t", target, "i")
        wait_screen(target, "empty insert before Ctrl+C", lambda s: "INSERT" in s)
        tmux("send-keys", "-t", target, "C-c")
        screen = wait_screen(target, "empty insert after Ctrl+C", lambda s: "NORMAL" in s)
        assert "press Ctrl+C again to exit" not in screen

        tmux("send-keys", "-t", target, "C-c")
        wait_screen(target, "empty normal armed", lambda s: "press Ctrl+C again to exit" in s)
        tmux("send-keys", "-t", target, "C-c")
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and tmux("has-session", "-t", session, check=False).returncode == 0:
            time.sleep(0.05)
        assert tmux("has-session", "-t", session, check=False).returncode != 0, "second Ctrl+C did not exit Yuke"
finally:
    tmux("kill-session", "-t", session, check=False)
    with tempfile.NamedTemporaryFile(prefix="yuke-ctrl-c-", suffix=".txt", mode="w", delete=False) as artifact:
        artifact.write("\n".join(transcript))
        print("Saved Ctrl+C transcript:", artifact.name)

print("Ctrl+C tmux check passed")
