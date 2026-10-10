#!/usr/bin/env python3
"""Check /exit, /close, and quit guards in isolated Yuke TUI sessions."""
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
plugin = pathlib.Path(__file__).resolve().parents[1] / "plugins" / "exit-command.js"
transcript = []


def tmux(*args, check=True):
    return subprocess.run(
        [TMUX, *args], check=check, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )


def wait_screen(target, label, text, timeout=5):
    deadline = time.monotonic() + timeout
    screen = ""
    while time.monotonic() < deadline:
        screen = tmux("capture-pane", "-t", target, "-p", "-S", "-28").stdout
        if text in screen:
            transcript.append(f"=== {label} ===\n{screen}")
            return screen
        time.sleep(0.05)
    transcript.append(f"=== {label} (timeout) ===\n{screen}")
    raise AssertionError(f"timed out at {label}\n{screen}")


def run_case(command, guarded):
    case = command + (": guarded" if guarded else ": direct")
    session = "yuke-exit-" + uuid.uuid4().hex[:10]
    try:
        with tempfile.TemporaryDirectory(prefix="yuke-exit-") as directory:
            root = pathlib.Path(directory)
            profile = root / "config" / "yuke"
            profile.mkdir(parents=True)
            source = (
                'import { plugins } from "yuke";\n'
                f'import {{ exitCommand }} from {json.dumps(str(plugin))};\n'
                'plugins.use(exitCommand);\n'
            )
            if guarded:
                source += (
                    'plugins.use({ name: "exit-check", apply(ctx) {\n'
                    '  let held = false;\n'
                    '  ctx.on("quit.request", () => {\n'
                    '    if (held) return false;\n'
                    '    held = true;\n'
                    '    ctx.interaction.notify("exit held by test guard");\n'
                    '    return true;\n'
                    '  });\n'
                    '}});\n'
                )
            (profile / "index.js").write_text(source)
            result = root / "exit-code"
            run = root / "run.sh"
            run.write_text(
                "#!/bin/sh\n"
                f"export XDG_CONFIG_HOME={json.dumps(str(root / 'config'))}\n"
                f"export XDG_DATA_HOME={json.dumps(str(root / 'data'))}\n"
                f"export XDG_STATE_HOME={json.dumps(str(root / 'state'))}\n"
                f"export XDG_CACHE_HOME={json.dumps(str(root / 'cache'))}\n"
                "export YUKE_APPNAME=yuke\n"
                "export TERM=xterm-256color\n"
                f"cd {json.dumps(str(root))}\n"
                f"{json.dumps(YUKE)}\n"
                f"printf '%s\\n' \"$?\" > {json.dumps(str(result))}\n"
            )
            run.chmod(0o700)
            tmux("new-session", "-d", "-x", "100", "-y", "28", "-s", session, str(run))
            target = tmux("list-panes", "-t", session, "-F", "#{pane_id}").stdout.strip()
            wait_screen(target, f"{case}: initial chat", "type a message to start the session")
            tmux("send-keys", "-t", target, "C-p")
            wait_screen(target, f"{case}: command palette", "exit Yuke")
            tmux("send-keys", "-t", target, "Escape")
            tmux("send-keys", "-t", target, "-l", command)
            screen = wait_screen(target, f"{case}: slash menu", command)
            assert "exit Yuke" in screen, f"{command} was not listed"
            tmux("send-keys", "-t", target, "Enter")
            if guarded:
                wait_screen(target, f"{case}: quit held", "exit held by test guard")
                assert not result.exists(), f"{command} bypassed the quit guard"
                tmux("send-keys", "-t", target, "-l", command)
                wait_screen(target, f"{case}: second slash menu", command)
                tmux("send-keys", "-t", target, "Enter")
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                if result.exists() and tmux("has-session", "-t", session, check=False).returncode != 0:
                    break
                time.sleep(0.05)
            else:
                raise AssertionError(f"{case}: {command} did not end the Yuke process and tmux session")
            assert result.read_text().strip() == "0", f"{case}: Yuke did not exit cleanly"
            transcript.append(f"=== {case}: Yuke exited with code 0; tmux session ended ===\n")
    finally:
        tmux("kill-session", "-t", session, check=False)


try:
    for command in ("/exit", "/close"):
        run_case(command, False)
        run_case(command, True)
finally:
    with tempfile.NamedTemporaryFile(prefix="yuke-exit-", suffix=".txt", mode="w", delete=False) as artifact:
        artifact.write("\n".join(transcript))
        print("Saved exit-command transcript:", artifact.name)

print("/exit and /close tmux checks passed")
