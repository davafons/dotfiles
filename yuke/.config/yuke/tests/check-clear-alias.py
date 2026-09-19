#!/usr/bin/env python3
"""Check that /clear delegates to chat:new in an isolated Yuke TUI."""
import json
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
plugin = pathlib.Path(__file__).resolve().parents[1] / "plugins" / "clear-alias.js"
session = "yuke-clear-" + uuid.uuid4().hex[:10]
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


def wait_screen(target, label, text, timeout=5):
    deadline = time.monotonic() + timeout
    screen = ""
    while time.monotonic() < deadline:
        screen = capture(target, label)
        if text in screen:
            return screen
        transcript.pop()
        time.sleep(0.05)
    raise AssertionError(f"timed out at {label}\n{screen}")


try:
    with tempfile.TemporaryDirectory(prefix="yuke-clear-") as directory:
        root = pathlib.Path(directory)
        profile = root / "config" / "yuke"
        profile.mkdir(parents=True)
        (profile / "index.js").write_text(
            'import { plugins } from "yuke";\n'
            f'import {{ clearAlias }} from {json.dumps(str(plugin))};\n'
            'plugins.use(clearAlias);\n'
            'plugins.use({ name: "clear-check", apply(ctx) {\n'
            '  ctx.inject(["tui"], c => c.tui.command.add("chat:new", {\n'
            '    run: () => c.interaction.notify("clear delegated to chat:new"),\n'
            '  }));\n'
            '}});\n'
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
        wait_screen(target, "initial chat", "type a message to start the session")
        tmux("send-keys", "-t", target, "-l", "/clear")
        screen = wait_screen(target, "slash menu", "/clear")
        assert "leave the session and start empty" in screen, "/clear was not listed"
        tmux("send-keys", "-t", target, "Enter")
        screen = wait_screen(target, "delegated command", "clear delegated to chat:new")
        assert "/clear" not in screen, "the command draft was not cleared"
finally:
    tmux("kill-session", "-t", session, check=False)
    with tempfile.NamedTemporaryFile(prefix="yuke-clear-", suffix=".txt", mode="w", delete=False) as artifact:
        artifact.write("\n".join(transcript))
        print("Saved /clear transcript:", artifact.name)

print("/clear alias tmux check passed")
