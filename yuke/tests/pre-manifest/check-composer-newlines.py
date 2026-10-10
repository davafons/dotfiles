#!/usr/bin/env python3
"""Check Shift+Enter and Ctrl+J from a Ghostty-format tmux client into Yuke."""
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
profile_root = pathlib.Path(__file__).resolve().parents[1]
plugin = profile_root / "plugins" / "vim-improved.js"
prompt_history = profile_root / "plugins" / "prompt-history.js"
tmux_config = pathlib.Path.home() / ".config" / "tmux" / "tmux.conf"
socket = "yuke-newlines-" + uuid.uuid4().hex[:10]
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
    with tempfile.TemporaryDirectory(prefix="yuke-newlines-") as directory:
        root = pathlib.Path(directory)
        profile = root / "config" / "yuke"
        profile.mkdir(parents=True)
        (profile / "index.js").write_text(
            'import { plugins } from "yuke";\n'
            'import { currentPane } from "yuke:session";\n'
            f'import {{ vimImproved }} from {json.dumps(str(plugin))};\n'
            f'import {{ promptHistory }} from {json.dumps(str(prompt_history))};\n'
            'plugins.use(vimImproved);\n'
            'plugins.use(promptHistory);\n'
            'plugins.use({ name: "history-key-fixture", apply(ctx) { ctx.inject(["tui"], () => {\n'
            '  const view = currentPane(); if (!view) throw new Error("no pane");\n'
            '  view.transcript.partsOf = (id) => id === 1 ? [{ id: 0, type: "text", text: "ghostty history prompt" }] : [];\n'
            '  view.transcript.setOutline([{ id: 1, type: "user" }], null);\n'
            '}); }});\n'
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
        wait_screen("initial normal", "NORMAL")

        # Ghostty sends legacy VT/LF for Ctrl+K/J; tmux's extended-key protocol must
        # preserve them as immediate normal-mode history controls.
        send(b"\x0b")
        wait_screen("Ctrl+K history through Ghostty", "▪ ghostty history prompt", timeout=0.5)
        send(b"\x0a")
        time.sleep(0.1)
        screen = capture("Ctrl+J restores draft through Ghostty")
        assert "▪ ghostty history prompt" not in screen, "Ctrl+J did not leave the recalled prompt"
        assert "NORMAL" in screen and "ctrl+k" not in screen.lower(), "history controls left a pending chord"

        send(b"i")
        send(b"shift first")
        # This is the CSI-u sequence from Ghostty's shift+enter binding.
        send(b"\x1b[13;2u")
        send(b"shift second")
        screen = wait_screen("Shift+Enter newline", "› shift first\n  shift second")
        assert "new chat failed" not in screen, "Shift+Enter submitted the composer"

        # Ghostty sends the legacy LF byte for Ctrl+J. Tmux must preserve it as Ctrl+J.
        send(b"\x0a")
        send(b"ctrl third")
        screen = wait_screen("Ctrl+J newline", "› shift first\n  shift second\n  ctrl third")
        assert "new chat failed" not in screen, "Ctrl+J submitted the composer"
        assert "INSERT" in screen, "newline keys must keep insert mode"
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
    with tempfile.NamedTemporaryFile(prefix="yuke-newlines-", suffix=".txt", mode="w", delete=False) as artifact:
        artifact.write("\n".join(transcript))
        print("Saved composer newline transcript:", artifact.name)

print("Composer newline Ghostty-to-tmux check passed")
