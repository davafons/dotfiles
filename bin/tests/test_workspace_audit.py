"""Exercise the read-only audit against real private jj repositories."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / "agents/.agents/davstack/skills/dav-mode/scripts/workspace-audit.py"


class WorkspaceAudit(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="davstack-audit-")
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name).resolve()
        config = self.directory / "jj.toml"
        config.write_text('[user]\nname="Tests"\nemail="tests@example.invalid"\n[signing]\nbehavior="drop"\n')
        self.env = {**os.environ, "JJ_CONFIG": str(config), "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"}
        self.root = self.directory / "project with spaces"
        self.run_command(["jj", "git", "init", "--colocate", str(self.root)], self.directory)
        (self.root / "file with spaces.txt").write_text("baseline\n")
        self.run_command(["jj", "describe", "-m", "Baseline"])
        self.run_command(["jj", "bookmark", "create", "main", "-r", "@"])
        self.run_command(["jj", "new", "main"])
        self.other = self.directory / 'odd " linked checkout'
        self.run_command(["jj", "workspace", "add", "--name", "linked", "-r", "main", str(self.other)])

    def run_command(self, argv, cwd=None):
        return subprocess.run(argv, cwd=cwd or self.root, env=self.env, capture_output=True, text=True, check=True, timeout=60).stdout

    def operation(self):
        return self.run_command(["jj", "--ignore-working-copy", "--at-operation=@", "op", "log", "--no-graph", "-T", 'id ++ "\\n"'])

    def test_unsnapshotted_bytes_are_reported_without_history_mutation(self):
        (self.other / "file with spaces.txt").write_text("not snapshotted\n")
        before = self.operation()
        result = json.loads(self.run_command(["python3", str(AUDIT), str(self.root), "--check-live-files"]))
        rows = {row["name"]: row for row in result["workspaces"]}
        self.assertEqual(rows["linked"]["path"], str(self.other))
        self.assertEqual(rows["linked"]["captured_changed_files"], 0)
        self.assertEqual(rows["linked"]["live_files"]["changed"], ["file with spaces.txt"])
        self.assertEqual(rows["linked"]["live_files"]["untracked_and_ignored"], "not audited")
        self.assertEqual(rows["linked"]["bucket"], "hold-work")
        self.assertEqual(rows["default"]["bucket"], "hold-primary-or-current")
        self.assertEqual(self.operation(), before)
        self.assertEqual((self.other / "file with spaces.txt").read_text(), "not snapshotted\n")

    def test_pinned_and_unknown_usage_never_become_safe(self):
        before = self.operation()
        held = json.loads(self.run_command(["python3", str(AUDIT), str(self.root), "--active", "linked"]))
        row = next(row for row in held["workspaces"] if row["name"] == "linked")
        self.assertEqual(row["bucket"], "hold-in-use")
        self.assertEqual(row["usage"], "active or pinned per supplied set")
        unknown = json.loads(self.run_command(["python3", str(AUDIT), str(self.root)]))
        row = next(row for row in unknown["workspaces"] if row["name"] == "linked")
        self.assertEqual(row["bucket"], "verify-usage-and-disk")
        self.assertEqual(row["usage"], "unknown")
        self.assertEqual(row["live_files"], "not checked")
        self.assertEqual(row["pr_state"], "not queried")
        self.assertEqual(self.operation(), before)

    def test_plain_directory_and_missing_base_fail_without_writes(self):
        plain = self.directory / "plain"
        plain.mkdir()
        before = self.operation()
        for path, extra in ((plain, []), (self.root, ["--base", "missing-base"])):
            result = subprocess.run(["python3", str(AUDIT), str(path), *extra], env=self.env, capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
        self.assertEqual(list(plain.iterdir()), [])
        self.assertEqual(self.operation(), before)


if __name__ == "__main__":
    unittest.main()
