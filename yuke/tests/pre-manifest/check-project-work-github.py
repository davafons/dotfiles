#!/usr/bin/env python3
"""Verify read-only gh requests, cursor pages, review/CI data, and project binding."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
HELPER = HERE.parent / "plugins/project-work-github.py"

class GitHubReadTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="yuke-github-read-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / "gh").symlink_to(HERE / "work-github-fixture.py")
        self.log = self.root / "requests.jsonl"
        self.env = {**os.environ, "PATH": str(self.root) + os.pathsep + os.environ["PATH"], "GH_REPO": "foreign/repo", "GH_FIXTURE_LOG": str(self.log)}

    def call(self, **args):
        result = subprocess.run(["python3", str(HELPER), json.dumps({"root": str(self.root), **args})], env=self.env, capture_output=True, text=True)
        if result.returncode:
            raise ValueError(result.stderr.strip())
        return json.loads(result.stdout)

    def test_cursor_reads_preserve_remote_status_and_never_mutate(self):
        first = self.call(action="list")
        second = self.call(action="list", cursor=first["next_cursor"])
        self.assertEqual(first["total"], 23)
        self.assertEqual(len({item["number"] for item in first["items"] + second["items"]}), 23)
        self.assertFalse(second["has_next"])
        pr = self.call(action="get", kind="pulls", number=18)["item"]
        self.assertEqual(pr["review"], "CHANGES_REQUESTED")
        self.assertEqual(pr["ci"], "FAILURE")
        self.assertEqual([check["status"] for check in pr["checks"]], ["FAILURE", "SUCCESS"])
        self.assertNotIn("\x1b", pr["body"])
        merged = self.call(action="list", kind="pulls", state="closed")
        self.assertEqual(merged["items"][0]["state"], "MERGED")
        for command in map(json.loads, self.log.read_text().splitlines()):
            self.assertIn(command[:2], (["repo", "view"], ["api", "graphql"]))
            self.assertFalse(any("mutation" in arg for arg in command))

    def test_bad_requests_and_auth_errors_do_not_report_success(self):
        for args in ({"action": "close"}, {"action": "get", "number": 0}, {"action": "list", "kind": "anything"}, {"action": "list", "token": "hidden"}, {"action": "list", "repo": "../bad"}):
            with self.assertRaises(ValueError):
                self.call(**args)
        self.assertFalse(self.log.exists(), "invalid inputs must not start gh")
        with self.assertRaisesRegex(ValueError, "not found"):
            self.call(action="get", number=999)
        self.env["GH_FIXTURE_FAIL"] = "1"
        with self.assertRaisesRegex(ValueError, "401"):
            self.call(action="list")

if __name__ == "__main__":
    unittest.main()
