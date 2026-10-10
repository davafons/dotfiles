#!/usr/bin/env python3
"""Check that /reload replaces profile plugins from changed source in an isolated TUI."""
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
reloader = pathlib.Path(__file__).resolve().parents[1] / "plugins" / "profile-reloader.js"
socket = "yuke-profile-reload-" + uuid.uuid4().hex[:10]
transcript = []


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
    raise AssertionError(f"timed out at {label}: missing {text!r}\n{screen}")


def profile_source(marker):
    return (
        'import { } from "yuke";\n'
        '/** @import { Plugin } from "yuke" */\n'
        'export const profile = /** @type {Plugin} */ ({ name: "user-profile", apply(ctx) {\n'
        '  ctx.inject(["tui"], c => c.tui.status.add({ side: "left", order: -100,\n'
        f'    render: () => {json.dumps(marker)} }}));\n'
        '}});\n'
    )


try:
    with tempfile.TemporaryDirectory(prefix="yuke-profile-reload-") as directory:
        root = pathlib.Path(directory)
        profile = root / "config" / "yuke"
        (profile / "plugins").mkdir(parents=True)
        (profile / "tools").mkdir()
        shutil.copyfile(reloader, profile / "plugins" / "profile-reloader.js")
        (profile / "profile.js").write_text(profile_source("PROFILE-V1"))
        (profile / "index.js").write_text(
            'import { plugins } from "yuke";\n'
            'import { profileReloader } from "./plugins/profile-reloader.js";\n'
            'plugins.use(profileReloader);\n'
        )
        run = root / "run.sh"
        run.write_text(
            "#!/bin/sh\n"
            f"export XDG_CONFIG_HOME={json.dumps(str(root / 'config'))}\n"
            f"export XDG_DATA_HOME={json.dumps(str(root / 'data'))}\n"
            f"export XDG_STATE_HOME={json.dumps(str(root / 'state'))}\n"
            f"export XDG_CACHE_HOME={json.dumps(str(root / 'cache'))}\n"
            "unset HERDR_ENV HERDR_PANE_ID HERDR_SOCKET_PATH\n"
            "export TERM=xterm-256color\n"
            f"exec {json.dumps(YUKE)}\n"
        )
        run.chmod(0o700)
        tmux("new-session", "-d", "-x", "100", "-y", "28", "-s", "test", str(run))
        wait_screen("initial profile", "PROFILE-V1")

        (profile / "profile.js").write_text(profile_source("PROFILE-V2"))
        tmux("send-keys", "-t", "test", "-l", "/reload")
        wait_screen("first reload command", "reload profile plugins, AGENTS.md, and skills")
        tmux("send-keys", "-t", "test", "Enter")
        screen = wait_screen("first reloaded profile", "PROFILE-V2")
        assert "PROFILE-V1" not in screen, "the first profile status entry survived reload"

        # A second reload must bypass both the startup module and the first fresh module.
        (profile / "profile.js").write_text(profile_source("PROFILE-V3"))
        tmux("send-keys", "-t", "test", "-l", "/reload")
        wait_screen("second reload command", "reload profile plugins, AGENTS.md, and skills")
        tmux("send-keys", "-t", "test", "Enter")
        screen = wait_screen("second reloaded profile", "PROFILE-V3")
        assert "PROFILE-V2" not in screen, "the second profile status entry survived reload"

        # Invalid fresh source must leave the last working profile active.
        (profile / "profile.js").write_text("this is not valid JavaScript }\n")
        tmux("send-keys", "-t", "test", "-l", "/reload")
        wait_screen("failed reload command", "reload profile plugins, AGENTS.md, and skills")
        tmux("send-keys", "-t", "test", "Enter")
        screen = wait_screen("failed reload", "Profile reload failed")
        assert "PROFILE-V3" in screen, "a failed import removed the working profile"
finally:
    tmux("kill-server", check=False)
    with tempfile.NamedTemporaryFile(prefix="yuke-profile-reload-", suffix=".txt", mode="w", delete=False) as artifact:
        artifact.write("\n".join(transcript))
        print("Saved profile reload transcript:", artifact.name)

print("Profile /reload tmux check passed")
