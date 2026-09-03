import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


WRAPPER = Path(__file__).parents[1] / "bin" / "playwright-cli"


class BackgroundBrowser(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="playwright-focus-")
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.log = self.root / "calls.jsonl"
        self.env_file = self.root / "env"
        self.env_file.write_text("export PLAYWRIGHT_MCP_EXTENSION_TOKEN=synthetic-test-token\n")
        backend = self.root / "npx"
        backend.write_text(f"#!{sys.executable}\n" + '''import json, os, sys
from pathlib import Path
args = sys.argv[3:]
with open(os.environ["FOCUS_TEST_LOG"], "a") as log:
    log.write(json.dumps(["cli", *args]) + "\\n")
mode = os.environ.get("FOCUS_TEST_SESSION", "missing")
if args == ["list", "--json"]:
    print(json.dumps({"browsers": [] if mode == "missing" else [{"name": "focus-test", "status": "open", "attached": mode != "unattached"}]}))
elif "tab-list" in args:
    if mode == "missing":
        sys.exit(1)
    print("0: chrome-extension://mmlmfjhmonkocbjadbfplnigmagldckm/connect.html" if mode == "welcome" else "0: https://example.test/")
else:
    print("synthetic backend: " + " ".join(args))
''')
        backend.chmod(0o755)
        aerospace = self.root / "aerospace"
        aerospace.write_text(f"#!{sys.executable}\n" + '''import json, os, sys
with open(os.environ["FOCUS_TEST_LOG"], "a") as log:
    log.write(json.dumps(["aerospace", *sys.argv[1:]]) + "\\n")
print("60" if "list-windows" in sys.argv else "1")
''')
        aerospace.chmod(0o755)

    def run_wrapper(self, *args, session="missing"):
        script = WRAPPER.read_text()
        assignment = 'ENV_FILE="${HOME}/.config/playwright-cli/env"'
        self.assertEqual(script.count(assignment), 1)
        script = script.replace(assignment, 'ENV_FILE="${FOCUS_TEST_ENV_FILE}"')
        env = {**os.environ, "PATH": f"{self.root}:/opt/homebrew/bin:/usr/bin:/bin",
               "FOCUS_TEST_LOG": str(self.log), "FOCUS_TEST_ENV_FILE": str(self.env_file),
               "FOCUS_TEST_SESSION": session, "PLAYWRIGHT_CLI_SESSION": "focus-test"}
        result = subprocess.run(["/bin/bash", "-c", script, str(WRAPPER), *args], env=env,
                                capture_output=True, text=True, timeout=10)
        calls = [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []
        return result, calls

    def test_fresh_attach_stops_before_handshake_or_focus_change(self):
        result, calls = self.run_wrapper("attach", "--extension")
        self.assertEqual(result.returncode, 75, result.stdout + result.stderr)
        self.assertIn("--allow-foreground", result.stderr)
        self.assertFalse(any("attach" in call or call[0] == "aerospace" for call in calls))

    def test_verified_attached_session_is_reused_without_focus(self):
        for session in ("open", "welcome"):
            with self.subTest(session=session):
                result, calls = self.run_wrapper("attach", "--extension", session=session)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("reusing attached", result.stdout)
                self.assertFalse(any("attach" in call or call[0] == "aerospace" for call in calls))

    def test_open_but_unattached_session_is_not_reused(self):
        result, calls = self.run_wrapper("attach", "--extension", session="unattached")
        self.assertEqual(result.returncode, 75, result.stdout + result.stderr)
        self.assertFalse(any("attach" in call or call[0] == "aerospace" for call in calls))

    def test_known_foreground_commands_are_opt_in(self):
        for command in ("open", "tab-new", "tab-select", "recording-start", "show"):
            with self.subTest(command=command):
                result, calls = self.run_wrapper(command, "1")
                self.assertEqual(result.returncode, 75, result.stdout + result.stderr)
                self.assertFalse(calls)

    def test_opt_in_is_consumed_and_never_restores_stale_focus(self):
        result, calls = self.run_wrapper("--allow-foreground", "attach", "--extension")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(["cli", "attach", "--extension=chrome", "--session=focus-test"], calls)
        self.assertFalse(any("--allow-foreground" in call or call[0] == "aerospace" for call in calls))

    def test_foreground_tab_selection_remains_available(self):
        result, calls = self.run_wrapper("--allow-foreground", "tab-select", "2")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls, [["cli", "-s=focus-test", "tab-select", "2"]])

    def test_explicit_session_option_does_not_bypass_guard(self):
        result, calls = self.run_wrapper("-s=focus-test", "tab-select", "2")
        self.assertEqual(result.returncode, 75, result.stdout + result.stderr)
        self.assertFalse(calls)

    def test_background_reads_remain_available(self):
        result, calls = self.run_wrapper("snapshot")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls, [["cli", "-s=focus-test", "snapshot"]])

    def test_text_arguments_are_not_commands_or_permission(self):
        result, calls = self.run_wrapper("fill", "e2", "attach")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls, [["cli", "-s=focus-test", "fill", "e2", "attach"]])
        result, calls = self.run_wrapper("fill", "e2", "--allow-foreground")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls[-1], ["cli", "-s=focus-test", "fill", "e2", "--allow-foreground"])

    def test_command_help_does_not_need_foreground_permission(self):
        result, calls = self.run_wrapper("tab-new", "--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls, [["cli", "-s=focus-test", "tab-new", "--help"]])


if __name__ == "__main__":
    unittest.main()
