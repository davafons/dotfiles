#!/usr/bin/env python3
"""Verify concurrent alias edits and preservation of invalid files."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HELPER = Path(__file__).resolve().parents[1] / ".config/yuke/plugins/model-alias-store.py"


def request(alias, revision=0):
    return {"version": 1, "revision": revision, "presets": [{"alias": alias, "model": "probe/model", "effort": "high"}]}


class AliasStoreTests(unittest.TestCase):
    def test_only_one_writer_can_replace_a_revision(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model-aliases.json"
            workers = [subprocess.Popen([sys.executable, str(HELPER), str(path), json.dumps(request(alias))],
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                       for alias in ("one", "two")]
            results = [worker.communicate(timeout=10) for worker in workers]
            self.assertEqual(sorted(worker.returncode for worker in workers), [0, 1])
            winner = next(json.loads(stdout) for worker, (stdout, _) in zip(workers, results) if worker.returncode == 0)
            self.assertEqual(json.loads(path.read_text()), winner)
            self.assertEqual(winner["revision"], 1)
            self.assertIn("changed in another Yuke", next(stderr for worker, (_, stderr) in zip(workers, results) if worker.returncode != 0))
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            emptied = subprocess.run([sys.executable, str(HELPER), str(path), json.dumps({"version": 1, "revision": 1, "presets": []})], capture_output=True, text=True)
            self.assertEqual(emptied.returncode, 0, emptied.stderr)
            self.assertEqual(json.loads(path.read_text())["presets"], [])

    def test_bad_file_and_symlink_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model-aliases.json"
            path.write_text("not valid JSON\n")
            result = subprocess.run([sys.executable, str(HELPER), str(path), json.dumps(request("one"))], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(path.read_text(), "not valid JSON\n")
            path.unlink()
            target = Path(directory) / "untouched.json"
            target.write_text(json.dumps({"version": 1, "revision": 0, "presets": []}))
            original = target.read_bytes()
            path.symlink_to(target)
            result = subprocess.run([sys.executable, str(HELPER), str(path), json.dumps(request("one"))], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(path.is_symlink())
            self.assertEqual(target.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
