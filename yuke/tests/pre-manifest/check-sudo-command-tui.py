#!/usr/bin/env python3
"""Check the real approval and password dialogs in an isolated detached terminal."""
import argparse
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time
import uuid

TMUX = shutil.which("tmux")
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--binary", default=shutil.which("yuke"))
YUKE = str(pathlib.Path(parser.parse_args().binary).resolve())
assert TMUX and YUKE
plugin = pathlib.Path(__file__).resolve().parents[1] / "plugins" / "sudo-command.js"
secret = "fixture-private-password-783"
wrong = "fixture-wrong-password-409"
captures = []
session = "yuke-sudo-" + uuid.uuid4().hex[:10]


def tmux(*args, check=True):
    return subprocess.run([TMUX, *args], check=check, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def screen_has(target, label, text):
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        screen = tmux("capture-pane", "-t", target, "-p", "-S", "-28").stdout
        assert secret not in screen and wrong not in screen, "password appeared on screen"
        if text in screen:
            captures.append(f"=== {label} ===\n{screen}")
            return screen
        time.sleep(0.05)
    raise AssertionError(f"timed out at {label}\n{screen}")


try:
    with tempfile.TemporaryDirectory(prefix="yuke-sudo-tui-") as directory:
        root = pathlib.Path(directory)
        profile = root / "config" / "yuke"
        (profile / "plugins").mkdir(parents=True)
        marker = root / "command-started"
        fake = root / "sudo"
        fake.write_text("#!" + sys.executable + "\n" +
            "import os, pathlib, subprocess, sys\n"
            "assert sys.argv[1:] == ['-k', '-A', '--', '/usr/bin/id', '-u']\n"
            "assert sys.stdin.read() == ''\n"
            "for attempt in range(3):\n"
            "    response = subprocess.run([os.environ['SUDO_ASKPASS']], capture_output=True)\n"
            "    if response.returncode: sys.exit(1)\n"
            f"    if response.stdout == {secret.encode() + b'\n'!r}:\n"
            f"        pathlib.Path({str(marker)!r}).write_text('fixture command ran once')\n"
            "        print('0')\n        sys.exit(0)\n"
            "    sys.stderr.write('Sorry, try again.\\n')\n"
            "sys.stderr.write('sudo: 3 incorrect password attempts\\n')\n"
            "sys.exit(1)\n"
        )
        fake.chmod(0o700)
        real_helper = plugin.with_suffix(".py")
        (profile / "plugins" / "sudo-command.py").write_text(
            "import importlib.util\n"
            f"spec = importlib.util.spec_from_file_location('helper', {str(real_helper)!r})\n"
            "module = importlib.util.module_from_spec(spec)\n"
            "spec.loader.exec_module(module)\n"
            "run = module.run\n"
            f"module.run = lambda request, **kwargs: run(request, {str(fake)!r}, **kwargs)\n"
            "raise SystemExit(module.main())\n"
        )
        (profile / "index.js").write_text(
            'import { plugins } from "yuke";\n'
            f'import {{ sudoCommand }} from {json.dumps(str(plugin))};\n'
            'plugins.use({ name: "sudo-test-driver", apply(ctx) {\n'
            ' let tool;\n'
            ' sudoCommand.apply({ get alive() { return ctx.alive; }, interaction: ctx.interaction,\n'
            '   effect: ctx.effect.bind(ctx), use: ctx.use.bind(ctx), inject: ctx.inject.bind(ctx), tools: { define(value) { tool = value; ctx.tools.define(value); } } });\n'
            ' ctx.inject(["tui"], c => c.tui.command.add("test", { slash: "sudo-test", desc: "Test sudo dialog",\n'
            '   args: true, run: async (argument) => { try { const result = await tool.execute({ timeout_ms: argument === "timeout" ? 1000 : 10000, argv: ["/usr/bin/id", "-u"], reason: "Test fixture only; no root command runs." }, ctx.signal,\n'
            f'     {{ workspaceRoot: {json.dumps(str(root))} }});\n'
            '     ctx.print("SUDO_TEST_RESULT " + JSON.stringify(result)); ctx.interaction.notify("sudo test finished");\n'
            '   } catch { ctx.interaction.notify("sudo test failed", "error"); } } }));\n'
            '}});\n'
        )
        run = root / "run.sh"
        run.write_text("#!/bin/sh\n" + "\n".join(
            f"export XDG_{name}_HOME={json.dumps(str(root / name.lower()))}" for name in ("CONFIG", "DATA", "STATE", "CACHE")
        ) + f"\nexport YUKE_APPNAME=yuke TERM=xterm-256color\ncd {json.dumps(str(root))}\nexec {json.dumps(YUKE)}\n")
        run.chmod(0o700)
        tmux("new-session", "-d", "-x", "100", "-y", "28", "-s", session, str(run))
        target = tmux("list-panes", "-t", session, "-F", "#{pane_id}").stdout.strip()
        screen_has(target, "startup", "type a message to start the session")

        def request(argument=""):
            time.sleep(0.15)
            tmux("send-keys", "-t", target, "C-l")
            tmux("send-keys", "-t", target, "-l", "/sudo-test" + (" " + argument if argument else ""))
            screen_has(target, "slash command", "/sudo-test")
            tmux("send-keys", "-t", target, "Enter")
            screen = screen_has(target, "approval", "Run as root?")
            assert '/usr/bin/id' in screen and 'Test fixture only' in screen

        request()
        tmux("send-keys", "-t", target, "Escape")
        screen_has(target, "declined", "sudo test finished")
        assert not marker.exists()
        request()
        tmux("send-keys", "-t", target, "Enter")
        screen_has(target, "password dialog", "Sudo password (local only)")
        tmux("send-keys", "-t", target, "-l", secret)
        time.sleep(0.15)
        screen = screen_has(target, "masked input", "Sudo password (local only)")
        assert secret[:8] not in screen
        tmux("send-keys", "-t", target, "Escape")
        screen_has(target, "password canceled", "sudo test finished")
        assert not marker.exists()
        def password_entry(value):
            tmux("send-keys", "-t", target, "-l", value)
            time.sleep(0.1)
            screen = tmux("capture-pane", "-t", target, "-p").stdout
            assert secret not in screen and wrong not in screen
            tmux("send-keys", "-t", target, "Enter")

        request()
        tmux("send-keys", "-t", target, "Enter")
        screen_has(target, "first attempt", "Sudo password (local only)")
        password_entry(wrong)
        screen_has(target, "second attempt", "attempt 2")
        assert not marker.exists()
        password_entry(wrong)
        screen_has(target, "third attempt", "attempt 3")
        assert not marker.exists()
        password_entry(secret)
        screen_has(target, "completed", "sudo test finished")
        assert marker.read_text() == "fixture command ran once"
        marker.unlink()
        request()
        tmux("send-keys", "-t", target, "Enter")
        screen_has(target, "exhaustion first attempt", "Sudo password (local only)")
        password_entry(wrong)
        screen_has(target, "exhaustion second attempt", "attempt 2")
        password_entry(wrong)
        screen_has(target, "exhaustion third attempt", "attempt 3")
        password_entry(wrong)
        screen_has(target, "attempts exhausted", "sudo test finished")
        assert not marker.exists()
        request()
        tmux("send-keys", "-t", target, "Enter")
        screen_has(target, "retry cancellation first attempt", "Sudo password (local only)")
        password_entry(wrong)
        screen_has(target, "retry cancellation second attempt", "attempt 2")
        tmux("send-keys", "-t", target, "Escape")
        screen_has(target, "retry canceled", "sudo test finished")
        assert not marker.exists()
        request("timeout")
        tmux("send-keys", "-t", target, "Enter")
        screen_has(target, "timeout first attempt", "Sudo password (local only)")
        password_entry(wrong)
        screen_has(target, "timeout retry", "attempt 2")
        screen = screen_has(target, "timeout closes retry dialog", "sudo test finished")
        assert "attempt 2" not in screen
        assert not marker.exists()
        log = (root / "state" / "yuke" / "yuke.log").read_text()
        assert secret not in log and wrong not in log
        assert 'SUDO_TEST_RESULT' in log and '\\"exit_code\\":0' in log
        assert '3 incorrect password attempts' in log
        assert '\\"timed_out\\":true' in log
        assert 'No command ran' in log
        tmux("kill-session", "-t", session, check=False)
        for path in (root / "state").rglob("*"):
            if path.is_file():
                assert secret.encode() not in path.read_bytes() and wrong.encode() not in path.read_bytes(), f"password persisted in {path}"
finally:
    tmux("kill-session", "-t", session, check=False)
    with tempfile.NamedTemporaryFile(prefix="yuke-sudo-dialogs-", suffix=".txt", mode="w", delete=False) as artifact:
        artifact.write("\n".join(captures))
        print("Saved sudo dialog captures:", artifact.name)

print("sudo approval, masked retries, exhaustion, cancellation, timeout, and state privacy checks passed")
