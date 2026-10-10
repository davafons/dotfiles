#!/usr/bin/env python3
"""Check shared project identity, durable checkpoints, concurrent edits, and privacy."""
import json
from pathlib import Path
import subprocess
import sqlite3
import tempfile
import unittest

HELPER = Path(__file__).resolve().parents[1] / "plugins/project-work-store.py"


class WorkStoreTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="yuke-work-store-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.repo = self.root / "repo"
        (self.repo / ".jj/repo").mkdir(parents=True)
        (self.repo / ".git").mkdir()
        self.other = self.root / "other"
        self.other.mkdir()
        self.database = self.root / "private/work.sqlite3"

    def command(self, action, root=None, session="source", **args):
        return ["python3", str(HELPER), str(self.database), json.dumps(
            dict(action=action, root=str(root or self.repo), session=session, **args))]

    def run_store(self, action, **args):
        return json.loads(subprocess.check_output(self.command(action, **args), text=True))

    def task(self, **args):
        return self.run_store("task", title="Fix focus", status="later", notes="Not tested yet", **args)

    def rejected(self, action, **args):
        result = subprocess.run(self.command(action, **args), capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        return result.stderr

    def test_linked_checkouts_share_tasks_but_nested_repositories_do_not(self):
        first = self.task(site="source:1:1")
        linked = self.root / "linked"
        (linked / ".jj").mkdir(parents=True)
        (linked / ".jj/repo").write_text("../.." + "/repo/.jj/repo")
        snapshot = self.run_store("list", root=linked)
        self.assertEqual(snapshot["tasks"][0]["id"], first["id"])
        self.assertEqual(snapshot["project"], "jj:" + str((self.repo / ".jj/repo").resolve()))
        self.assertEqual(self.task(site="source:1:1"), first, "replaying a tool call must not duplicate a task")
        nested = self.repo / "nested"
        (nested / ".git").mkdir(parents=True)
        self.assertEqual(self.run_store("list", root=nested)["tasks"], [])
        self.assertEqual(self.run_store("list", root=self.other)["tasks"], [])
        self.rejected("get", root=self.other, id=first["id"])
        self.assertEqual(self.database.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.database.parent.stat().st_mode & 0o777, 0o700)

    def test_git_worktrees_share_common_repository(self):
        original = self.root / "git-repo"
        metadata = original / ".git/worktrees/linked"
        metadata.mkdir(parents=True)
        (metadata / "commondir").write_text("../..\n")
        linked = self.root / "git-linked"
        linked.mkdir()
        (linked / ".git").write_text("gitdir: ../git-repo/.git/worktrees/linked\n")
        first = self.task(root=original)
        self.assertEqual(self.run_store("list", root=linked)["tasks"][0]["id"], first["id"])

    def test_concurrent_edits_require_a_fresh_version(self):
        task = self.task()
        commands = [self.command("task", id=task["id"], version=task["version"], title="Fix focus",
                                 status=status, notes="Keep this note") for status in ("now", "blocked")]
        processes = [subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for command in commands]
        results = [(process.communicate(), process.returncode) for process in processes]
        self.assertEqual(sorted(code for _, code in results), [0, 1])
        stored = self.run_store("get", id=task["id"])["task"]
        self.assertEqual(stored["version"], 2)
        self.assertEqual(stored["notes"], "Keep this note")
        self.assertEqual(stored["session"], "source", "a status edit must retain the original session link")
        self.assertIn("refresh", self.rejected("task", id=task["id"], version=1, title="Lost update", status="done", notes=""))
        self.run_store("context", version=0, goal="Fix navigation", notes="Keep the global key handler")
        self.rejected("context", version=0, goal="Overwrite", notes="")
        self.assertEqual(self.run_store("list")["context"]["notes"], "Keep the global key handler")

    def test_checkpoint_freshness_and_task_status_are_independent(self):
        task = self.task()
        values = dict(summary="Regression passes; full suite has not run", next_step="Run the suite", verification="Focused test passes", task_id=task["id"])
        saved = self.run_store("checkpoint", **values)
        self.run_store("activity", observed_at=saved["updated"])
        self.assertFalse(self.run_store("get", id=task["id"])["checkpoint"]["stale"])
        self.run_store("activity", observed_at=saved["updated"] + 1)
        detail = self.run_store("get", id=task["id"])
        self.assertTrue(detail["checkpoint"]["stale"])
        self.assertEqual(detail["task"]["status"], "later", "saving progress must not mark the task done")
        self.run_store("checkpoint", session="new-session", **values)
        snapshot = self.run_store("list")
        self.assertEqual({c["session"] for c in snapshot["checkpoints"]}, {"source", "new-session"})
        self.assertEqual(snapshot["checkpoints"][0]["next_step"], "Run the suite")
        self.rejected("checkpoint", root=self.other, **values)
        self.rejected("checkpoint", session="", **values)

    def test_github_links_survive_status_edits_and_old_store_migration(self):
        self.database.parent.mkdir()
        with sqlite3.connect(self.database) as db:
            db.execute("CREATE TABLE tasks (id TEXT PRIMARY KEY, project TEXT, title TEXT, status TEXT, notes TEXT, session TEXT, root TEXT, site TEXT UNIQUE, updated INTEGER, version INTEGER)")
            db.execute("INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", ("legacy", "jj:" + str((self.repo / ".jj/repo").resolve()), "Existing work", "later", "Keep this", "source", str(self.repo), None, 1, 1))
        calls = [subprocess.Popen(self.command("list"), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(4)]
        for call in calls:
            stdout, stderr = call.communicate()
            self.assertEqual(call.returncode, 0, stderr)
            self.assertEqual(json.loads(stdout)["tasks"][0]["github_url"], "")
        url = "https://github.com/example/repo/issues/17"
        task = self.task(github_url=url)
        self.run_store("task", id=task["id"], version=1, title="Fix focus", status="done", notes="Verified locally")
        linked = self.run_store("linked", github_url=url)
        self.assertEqual(linked["total"], 1)
        self.assertEqual(linked["tasks"][0]["status"], "done")
        self.assertEqual(self.run_store("get", id=task["id"])["task"]["github_url"], url)
        self.assertEqual(self.run_store("linked", root=self.other, github_url=url)["tasks"], [])
        self.run_store("task", id=task["id"], version=2, title="Fix focus", status="done", notes="Verified locally", github_url="")
        self.assertEqual(self.run_store("linked", github_url=url)["tasks"], [])
        self.rejected("task", title="Unsafe link", status="later", notes="", github_url="javascript:alert(1)")

    def test_board_pages_each_status_and_filters_the_whole_project(self):
        for index in range(7):
            self.run_store("task", title=f"Active task {index}", status="now", notes="")
        self.run_store("task", title="Deferred task", status="later", notes="Find this phrase")
        self.run_store("task", title="Completed task", status="done", notes="")
        first = self.run_store("board")
        self.assertEqual(first["counts"], [7, 1, 0, 0, 1])
        self.assertEqual(len([task for task in first["tasks"] if task["status"] == "now"]), 5)
        self.assertFalse(any(task["status"] == "done" for task in first["tasks"]))
        second = self.run_store("board", offsets=[5, 0, 0, 0, 0], include_done=True)
        active = [task for task in first["tasks"] + second["tasks"] if task["status"] == "now"]
        self.assertEqual(len({task["id"] for task in active}), 7)
        self.assertTrue(any(task["status"] == "done" for task in second["tasks"]))
        filtered = self.run_store("board", query="find this")
        self.assertEqual([task["title"] for task in filtered["tasks"]], ["Deferred task"])
        self.rejected("board", offsets=[0])
        self.rejected("board", offsets=[0, -1, 0, 0, 0])

    def test_validation_and_paging_do_not_drop_work(self):
        for index in range(12):
            self.run_store("task", title=f"Task {index}", status="done" if index == 0 else "later", notes="A quote: ' and 日本語")
        first = self.run_store("list")
        second = self.run_store("list", offset=10)
        self.assertEqual(first["total"], 11)
        self.assertEqual(len(first["tasks"]), 10)
        self.assertEqual(len(second["tasks"]), 1)
        self.assertEqual(len({t["id"] for t in first["tasks"] + second["tasks"]}), 11)
        self.assertEqual(self.run_store("list", include_done=True)["total"], 12)
        for field, value in (("title", "bad\x1b[31m"), ("title", ""), ("status", "unknown"), ("notes", None), ("id", None)):
            args = dict(title="Bad task", status="later", notes="")
            args[field] = value
            self.rejected("task", **args)
        self.assertEqual(self.run_store("list", include_done=True)["total"], 12)
        self.rejected("list", include_done="yes")
        self.rejected("list", offset=-1)
        self.rejected("task", title="Title\nnext line", status="later", notes="")
        self.rejected("task", title="Title", status="later", notes="bad\u009b31m")


if __name__ == "__main__":
    unittest.main()
