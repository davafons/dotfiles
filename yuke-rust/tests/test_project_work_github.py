import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HELPER = Path(__file__).resolve().parents[1] / ".config/yuke-rust/helpers/project-work-github.py"
ITEM = {"number": 17, "title": "Fix", "url": "https://github.com/example/repo/pull/17", "state": "OPEN",
        "updatedAt": "2026-11-14T00:00:00Z", "author": {"login": "someone"}, "labels": {"nodes": []}, "body": ""}


class GitHubRead(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.calls = self.root / "calls.jsonl"
        gh = self.root / "bin/gh"
        gh.parent.mkdir()
        # The fake gh records each call and answers a repository view or one GraphQL item.
        gh.write_text(f"""#!{sys.executable}
import json, sys
with open({str(self.calls)!r}, "a") as calls:
    calls.write(json.dumps(sys.argv[1:]) + "\\n")
if sys.argv[1:3] == ["repo", "view"]:
    print(json.dumps({{"nameWithOwner": "example/checkout", "url": "https://github.com/example/checkout"}}))
else:
    item = {json.dumps(ITEM)!r}
    print(json.dumps({{"data": {{"repository": {{"issue": json.loads(item), "pullRequest": json.loads(item)}}}}}}))
""")
        gh.chmod(0o700)

    def tearDown(self):
        self.directory.cleanup()

    def read(self, **args):
        environment = dict(os.environ, PATH=f"{self.root / 'bin'}:{os.environ['PATH']}")
        result = subprocess.run([sys.executable, str(HELPER), json.dumps(dict(args, root=str(self.root)))],
                                capture_output=True, text=True, env=environment)
        calls = [json.loads(line) for line in self.calls.read_text().splitlines()] if self.calls.exists() else []
        return result, calls

    def test_url_get_reads_the_linked_repository_kind_and_number(self):
        result, calls = self.read(action="get", kind="issues", url="https://github.com/example/repo/pull/17")
        self.assertEqual(result.returncode, 0, result.stderr)
        reply = json.loads(result.stdout)
        self.assertEqual([reply["repo"], reply["kind"], reply["item"]["number"]], ["example/repo", "pulls", 17])
        self.assertEqual(len(calls), 1)
        self.assertIn("number=17", calls[0])
        self.assertIn("name=repo", calls[0])
        self.assertTrue(any("pullRequest(number: $number)" in arg for arg in calls[0]))

    def test_number_get_reads_the_checkout_repository(self):
        result, calls = self.read(action="get", kind="issues", number=17)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["repo"], "example/checkout")
        self.assertEqual(calls[0][:2], ["repo", "view"])

    def test_bad_urls_and_mismatches_fail_before_gh(self):
        for args in (dict(action="get", url="https://example.com/a/b/issues/1"),
                     dict(action="get", url="https://github.com/a/b/issues/0"),
                     dict(action="list", url="https://github.com/a/b/issues/1"),
                     dict(action="get", url="https://github.com/a/b/issues/1", number=2),
                     dict(action="get")):
            result, calls = self.read(**args)
            self.assertEqual(result.returncode, 1, args)
            self.assertEqual(calls, [], args)


if __name__ == "__main__":
    unittest.main()
