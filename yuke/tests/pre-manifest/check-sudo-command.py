#!/usr/bin/env python3
"""Test askpass isolation, redaction, bounded output, and helper cleanup without root."""
import contextlib
import importlib.util
import io
import json
import os
import pathlib
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

PLUGIN = pathlib.Path(__file__).resolve().parents[1] / "plugins" / "sudo-command.py"
spec = importlib.util.spec_from_file_location("sudo_command", PLUGIN)
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


class SudoCommandTest(unittest.TestCase):
    def test_resolve_keeps_argv_literal_and_runs_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            marker = root / "must-not-run"
            executable = root / "fixture-command"
            executable.write_text("#!/bin/sh\ntouch " + str(marker) + "\n")
            executable.chmod(0o700)
            self.assertEqual(helper.resolve_command(str(executable) + " 'two words'"), [str(executable), "two words"])
            for command in [str(executable) + "; touch " + str(marker), "-u root id", "id $(touch " + str(marker) + ")", "id *"]:
                with self.assertRaises(ValueError):
                    helper.resolve_command(command)
            self.assertFalse(marker.exists())

    def test_askpass_never_becomes_command_input(self):
        with tempfile.TemporaryDirectory(prefix="yuke-sudo-test-") as directory:
            root = pathlib.Path(directory)
            audit = root / "audit.json"
            fake = root / "sudo"
            fake.write_text("#!" + sys.executable + "\n" + '''
import json, os, pathlib, subprocess, sys
assert sys.argv[1:4] == ["-k", "-A", "--"]
assert sys.stdin.read() == ""
secret = subprocess.check_output([os.environ["SUDO_ASKPASS"], "Password:"])
assert secret.endswith(b"\\n")
assert secret.decode().strip() not in json.dumps(dict(os.environ))
address = pathlib.Path(os.environ["YUKE_SUDO_SOCKET"])
assert address.stat().st_mode & 0o777 == 0o600
assert address.parent.stat().st_mode & 0o777 == 0o700
assert secret not in pathlib.Path(os.environ["SUDO_ASKPASS"]).read_bytes()
pathlib.Path(os.environ["YUKE_SUDO_TEST_AUDIT"]).write_text(json.dumps({"address": str(address), "argv": sys.argv[4:]}))
sys.stdout.buffer.write(b"command stdout " + secret)
sys.stderr.buffer.write(b"command stderr " + secret)
sys.exit(7)
''')
            fake.chmod(0o700)
            os.environ["YUKE_SUDO_TEST_AUDIT"] = str(audit)
            try:
                result = helper.run({"argv": ["/usr/bin/printf", "a b", "$(not-a-shell)"], "password": "test-only-secret-921", "timeout_ms": 5000}, str(fake))
            finally:
                del os.environ["YUKE_SUDO_TEST_AUDIT"]
            self.assertEqual(result["exit_code"], 7)
            self.assertEqual(result["stdout"], "command stdout [REDACTED]\n")
            self.assertEqual(result["stderr"], "command stderr [REDACTED]\n")
            record = json.loads(audit.read_text())
            self.assertEqual(record["argv"], ["/usr/bin/printf", "a b", "$(not-a-shell)"])
            self.assertFalse(pathlib.Path(record["address"]).parent.exists())

    def test_password_retries_stay_in_one_sudo_process(self):
        with tempfile.TemporaryDirectory() as directory:
            fake = pathlib.Path(directory) / "sudo"
            fake.write_text("#!" + sys.executable + "\n" + '''
import os, subprocess, sys
assert sys.stdin.read() == ""
for attempt in range(3):
    response = subprocess.run([os.environ["SUDO_ASKPASS"]], capture_output=True)
    if response.returncode:
        sys.exit(8)
    if response.stdout == b"correct-test-password\\n":
        sys.stdout.write("command ran once\\n")
        sys.exit(7)
    sys.stderr.buffer.write(response.stdout)
sys.exit(1)
''')
            fake.chmod(0o700)
            for replies, code, prompts in [
                (["wrong-test-password-2", "correct-test-password"], 7, 2),
                (["wrong-test-password-2", "wrong-test-password-3"], 1, 2),
                ([""], 8, 1),
            ]:
                read_fd, write_fd = os.pipe()
                os.write(write_fd, "".join(json.dumps({"password": password}) + "\n" for password in replies).encode())
                os.close(write_fd)
                outgoing = io.StringIO()
                with os.fdopen(read_fd) as incoming, patch("sys.stdin", incoming), contextlib.redirect_stdout(outgoing):
                    result = helper.run({"argv": ["/usr/bin/id"], "password": "wrong-test-password-1", "timeout_ms": 5000}, str(fake))
                self.assertEqual(result["exit_code"], code)
                events = [json.loads(line) for line in outgoing.getvalue().splitlines()]
                self.assertEqual(events, [{"type": "password", "attempt": attempt + 2} for attempt in range(prompts)])
                self.assertEqual(result["stdout"], "command ran once\n" if code == 7 else "")
                self.assertEqual(result.get("canceled", False), code == 8)
                for password in ["wrong-test-password-1", *replies]:
                    if password:
                        self.assertNotIn(password, json.dumps(result) + outgoing.getvalue())

    def test_nopasswd_does_not_receive_password(self):
        with tempfile.TemporaryDirectory() as directory:
            fake = pathlib.Path(directory) / "sudo"
            fake.write_text("#!" + sys.executable + "\nimport sys\nassert sys.stdin.read() == ''\nprint('no authentication needed')\n")
            fake.chmod(0o700)
            result = helper.run({"argv": ["/usr/bin/id"], "password": "never-command-input", "timeout_ms": 1000}, str(fake))
            self.assertEqual(result["exit_code"], 0)
            self.assertEqual(result["stdout"], "no authentication needed\n")

    def test_redaction_spans_chunks_and_precedes_truncation(self):
        output = helper.Output("abcXYZ")
        output.feed(b"a" * (helper.LIMIT - 2) + b"ab")
        output.feed(b"cX")
        output.feed(b"YZ" + b"z" * helper.LIMIT)
        text = output.text()
        self.assertNotIn("abcXYZ", text)
        self.assertNotIn("ab", text)
        self.assertIn("Output truncated", text)
        self.assertLessEqual(len(output.kept), helper.LIMIT)
        for split in range(7):
            output = helper.Output("abcXYZ")
            output.feed(b"before " + b"abcXYZ"[:split])
            output.feed(b"abcXYZ"[split:] + b" after")
            self.assertEqual(output.text(), "before [REDACTED] after")

    def test_deadline_cleans_up_askpass_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            record = root / "socket"
            fake = root / "sudo"
            fake.write_text("#!" + sys.executable + "\nimport os, pathlib, time\npathlib.Path(" + repr(str(record)) + ").write_text(os.environ['YUKE_SUDO_SOCKET'])\ntime.sleep(10)\n")
            fake.chmod(0o700)
            result = helper.run({"argv": ["/usr/bin/id"], "password": "not-used", "timeout_ms": 1500}, str(fake))
            self.assertTrue(result["timed_out"])
            self.assertEqual(result["signal"], 15)
            self.assertFalse(pathlib.Path(record.read_text()).parent.exists())

    def test_signal_cancels_helper_and_removes_private_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            record = root / "socket"
            fake = root / "sudo"
            fake.write_text("#!" + sys.executable + "\nimport os, pathlib, time\npathlib.Path(" + repr(str(record)) + ").write_text(os.environ['YUKE_SUDO_SOCKET'])\ntime.sleep(10)\n")
            fake.chmod(0o700)
            driver = (
                "import importlib.util\n"
                f"spec = importlib.util.spec_from_file_location('helper', {str(PLUGIN)!r})\n"
                "module = importlib.util.module_from_spec(spec)\nspec.loader.exec_module(module)\n"
                "run = module.run\n"
                f"module.run = lambda request, **kwargs: run(request, {str(fake)!r}, **kwargs)\n"
                "raise SystemExit(module.main())\n"
            )
            child = subprocess.Popen([sys.executable, "-c", driver], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                child.stdin.write(json.dumps({"argv": ["/usr/bin/id"], "password": "cancel-private-secret", "timeout_ms": 10000}).encode())
                child.stdin.close()
                child.stdin = None
                deadline = time.monotonic() + 5
                while not record.exists():
                    self.assertLess(time.monotonic(), deadline, "fixture did not start")
                    time.sleep(0.02)
                child.send_signal(signal.SIGTERM)
                stdout, stderr = child.communicate(timeout=5)
                self.assertEqual(child.returncode, 130)
                self.assertNotIn(b"cancel-private-secret", stdout + stderr)
                self.assertFalse(pathlib.Path(record.read_text()).parent.exists())
            finally:
                if child.poll() is None:
                    child.kill()
                    child.communicate()

    def test_invalid_request_never_reports_secret(self):
        secret = "test-only-invalid-secret"
        result = subprocess.run([sys.executable, str(PLUGIN)], input=json.dumps({"password": secret}), text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn(secret, result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
