#!/usr/bin/env python3
"""Check shared tasks, legacy record preservation, concurrent edits, and privacy."""
import json
import fcntl
import contextlib
import socketserver
import threading
import time
import os
from unittest.mock import patch
from pathlib import Path
import subprocess
import sqlite3
import tempfile
import unittest

HELPER = Path(__file__).resolve().parents[1] / ".config/yuke/plugins/project-work-store.py"


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

    @contextlib.contextmanager
    def inventory(self, panes=None):
        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                request = json.loads(self.rfile.readline())
                self.wfile.write((json.dumps({"id": request["id"], "result": {"type": "pane_list", "panes": panes or []}}) + "\n").encode())
        with tempfile.TemporaryDirectory(prefix="wi-", dir="/tmp") as directory:
            path = str(Path(directory) / "inventory.sock")
            with socketserver.ThreadingUnixStreamServer(path, Handler) as server:
                worker = threading.Thread(target=server.serve_forever, daemon=True)
                worker.start()
                try:
                    with patch.dict(os.environ, {"HERDR_ENV": "1", "HERDR_SOCKET_PATH": path}):
                        yield
                finally:
                    server.shutdown()
                    worker.join(timeout=2)

    def command(self, action, root=None, session="source", **args):
        args.setdefault("api_version", 2)
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

    def test_progress_preserves_scope_and_replays_completion_once(self):
        task = self.run_store("task", title="Fix focus", status="now", notes="Keep the scope")
        first = self.run_store("progress", id=task["id"], version=task["version"], body="Focused check passes; full check unrun", status="review", site="progress:1")
        self.assertEqual(first["version"], 2)
        detail = self.run_store("get", id=task["id"])
        self.assertEqual(detail["task"]["notes"], "Keep the scope")
        self.assertEqual(detail["task"]["title"], "Fix focus")
        self.assertEqual(detail["task"]["owner_session"], "source")
        self.assertEqual(detail["task"]["status"], "review")
        self.assertEqual(detail["messages"][0]["body"], "Focused check passes; full check unrun")
        args = dict(id=task["id"], version=first["version"], body="All required checks pass", status="done", site="progress:2")
        completed = self.run_store("progress", **args)
        self.assertEqual(completed["version"], 3)
        detail = self.run_store("get", id=task["id"])
        self.assertEqual(detail["task"]["owner_session"], "")
        self.run_store("task", id=task["id"], version=3, title="Fix focus", status="now", notes="Keep the scope", session="other")
        self.assertEqual(self.run_store("progress", **args), completed)
        detail = self.run_store("get", id=task["id"])
        self.assertEqual(detail["task"]["version"], 4)
        self.assertEqual(detail["task"]["owner_session"], "other")
        self.assertEqual(detail["task"]["status"], "now")
        self.assertEqual(len(detail["messages"]), 2)

    def test_progress_rejects_stale_unowned_and_foreign_mutations(self):
        task = self.run_store("task", title="Fix focus", status="now", notes="Keep the scope")
        args = dict(id=task["id"], version=1, body="Still working", site="progress:1")
        self.assertIn("owner", self.rejected("progress", **args, session="other"))
        self.assertIn("project", self.rejected("progress", **args, root=self.other))
        result = self.run_store("progress", **args)
        self.assertEqual(result["status"], "now")
        self.assertIn("refresh", self.rejected("progress", **{**args, "site": "stale"}))
        self.run_store("release", id=task["id"], version=2)
        self.assertIn("owner", self.rejected("progress", **{**args, "version": 3, "site": "unowned"}))
        detail = self.run_store("get", id=task["id"])
        self.assertEqual(detail["task"]["version"], 3)
        self.assertEqual(len(detail["messages"]), 1)

    def test_progress_requires_a_stable_site_and_rejects_changed_replays(self):
        task = self.run_store("task", title="Fix focus", status="now", notes="Keep the scope")
        args = dict(id=task["id"], version=1, body="Still working", status="blocked", site="progress:1")
        self.run_store("progress", **args)
        for change in ({"body": "Different"}, {"status": "done"}, {"version": 2}, {"session": "other"}):
            self.assertIn("replay", self.rejected("progress", **{**args, **change}))
        for change in ({"site": ""}, {"session": ""}, {"version": True}, {"status": "invalid"}, {"notes": "Overwrite scope"}, {"body": "bad\x1btext"}):
            self.rejected("progress", **{**args, "site": "invalid", **change})
        detail = self.run_store("get", id=task["id"])
        self.assertEqual(detail["task"]["version"], 2)
        self.assertEqual(detail["task"]["notes"], "Keep the scope")
        self.assertEqual(len(detail["messages"]), 1)

    def test_progress_concurrency_and_message_conflicts_are_atomic(self):
        task = self.run_store("task", title="Fix focus", status="now", notes="Keep the scope")
        args = dict(id=task["id"], version=1, body="Progress", status="review")
        commands = [self.command("progress", **args, site=site) for site in ("a", "b")]
        processes = [subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for command in commands]
        results = [(process.communicate(), process.returncode) for process in processes]
        self.assertEqual(sorted(code for _, code in results), [0, 1])
        detail = self.run_store("get", id=task["id"])
        self.assertEqual(detail["task"]["version"], 2)
        self.assertEqual(len(detail["messages"]), 1)
        self.run_store("message", id=task["id"], body="Existing message", site="occupied")
        self.rejected("progress", **{**args, "version": 2, "status": "done", "site": "occupied"})
        detail = self.run_store("get", id=task["id"])
        self.assertEqual(detail["task"]["status"], "review")
        self.assertEqual(detail["task"]["version"], 2)
        self.assertEqual(detail["task"]["owner_session"], "source")
        self.assertEqual(len(detail["messages"]), 2)
        command = self.command("progress", **{**args, "version": 2, "site": "same"})
        processes = [subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(2)]
        results = [(process.communicate(), process.returncode) for process in processes]
        self.assertEqual([code for _, code in results], [0, 0])
        self.assertEqual(json.loads(results[0][0][0]), json.loads(results[1][0][0]))
        self.assertEqual(len(self.run_store("get", id=task["id"])["messages"]), 3)

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

    def test_removed_features_leave_historical_records_untouched(self):
        task = self.task()
        key = self.run_store("list")["project"]
        with sqlite3.connect(self.database) as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, goal TEXT, notes TEXT, version INTEGER);
                CREATE TABLE IF NOT EXISTS checkpoints (project TEXT, session TEXT, task_id TEXT, summary TEXT, next_step TEXT, verification TEXT, root TEXT, updated INTEGER, PRIMARY KEY(project, session));
                CREATE TABLE IF NOT EXISTS activity (project TEXT, session TEXT, started INTEGER, PRIMARY KEY(project, session));
            """)
            db.execute("INSERT OR REPLACE INTO projects VALUES (?, ?, ?, ?)", (key, "Historical goal", "Keep decisions", 7))
            db.execute("INSERT INTO checkpoints VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (key, "source", task["id"], "Historical progress", "Next", "Not run", str(self.repo), 1))
            db.execute("INSERT INTO activity VALUES (?, ?, ?)", (key, "source", 2))
            before = {table: db.execute(f"SELECT * FROM {table}").fetchall() for table in ("projects", "checkpoints", "activity")}
        for action in ("list", "board"):
            snapshot = self.run_store(action)
            self.assertEqual(snapshot["tasks"][0]["id"], task["id"])
            self.assertNotIn("context", snapshot)
            self.assertNotIn("checkpoints", snapshot)
        detail = self.run_store("get", id=task["id"])
        self.assertNotIn("checkpoint", detail)
        self.assertEqual(detail["messages"], [])
        for action in ("context", "checkpoint", "activity"):
            self.assertIn("unknown work action", self.rejected(action))
        self.run_store("notes", id=task["id"], version=1, notes="Task notes still work")
        self.run_store("message", id=task["id"], body="Task coordination still works")
        with sqlite3.connect(self.database) as db:
            after = {table: db.execute(f"SELECT * FROM {table}").fetchall() for table in before}
        self.assertEqual(after, before, "removing active features must not delete or rewrite historical records")

    def test_already_running_clients_keep_their_storage_contract(self):
        task = self.task()
        self.run_store("context", api_version=1, version=0, goal="Previous client", notes="Keep running")
        saved = self.run_store("checkpoint", api_version=1, task_id=task["id"], summary="Previous client", next_step="Reload when idle", verification="Not run")
        self.run_store("activity", api_version=1, observed_at=saved["updated"] + 1)
        legacy = json.loads(subprocess.check_output([
            "python3", str(HELPER), str(self.database),
            json.dumps(dict(action="list", root=str(self.repo), session="source")),
        ], text=True))
        self.assertEqual(legacy["context"]["goal"], "Previous client")
        self.assertEqual(legacy["checkpoints"][0]["summary"], "Previous client")
        self.assertTrue(self.run_store("get", api_version=1, id=task["id"])["checkpoint"]["stale"])
        self.assertNotIn("context", self.run_store("list"))
        self.assertNotIn("checkpoints", self.run_store("board"))
        self.assertNotIn("checkpoint", self.run_store("get", id=task["id"]))
        self.assertIn("unsupported work API", self.rejected("list", api_version=3))

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
            self.run_store("task", title=f"Active task {index}", status="now", notes="", session="")
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
        clamped = self.run_store("board", offsets=[999, 0, 0, 0, 0])
        self.assertEqual(clamped["offsets"][0], 5)
        self.assertEqual(len(clamped["tasks"]), 3)
        self.rejected("board", offsets=[0])
        self.rejected("board", offsets=[0, -1, 0, 0, 0])

    def test_claims_are_atomic_and_messages_do_not_overwrite_notes(self):
        task = self.task()
        commands = [self.command("claim", id=task["id"], version=1, session=owner) for owner in ("agent-a", "child-b")]
        processes = [subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for command in commands]
        results = [(process.communicate(), process.returncode) for process in processes]
        self.assertEqual(sorted(code for _, code in results), [0, 1])
        stored = self.run_store("get", id=task["id"])["task"]
        self.assertEqual(stored["status"], "now", "claiming starts the task")
        owner = stored["owner_session"]
        other = "child-b" if owner == "agent-a" else "agent-a"
        self.assertEqual(stored["owner_root"], str(self.repo.resolve()))
        self.assertEqual(stored["session"], "source", "claiming must preserve provenance")
        self.rejected("task", session=other, id=task["id"], version=stored["version"], title="Clash", status="done", notes="")
        self.rejected("release", session=other, id=task["id"], version=stored["version"])
        message = dict(id=task["id"], body="## Handoff\n\n- Please review `focus`.", site="message:1:1", session=other)
        first = self.run_store("message", **message)
        self.assertEqual(self.run_store("message", **message), first, "replayed messages must not duplicate")
        detail = self.run_store("get", id=task["id"])
        self.assertEqual(detail["messages"][0]["body"], message["body"])
        self.assertEqual(detail["messages"][0]["session"], other)
        self.assertEqual(detail["task"]["notes"], "Not tested yet")
        self.assertEqual(detail["task"]["version"], stored["version"])
        self.run_store("release", session=owner, id=task["id"], version=stored["version"])
        released = self.run_store("get", id=task["id"])["task"]
        self.assertEqual(released["owner_session"], "")
        self.run_store("claim", session=other, id=task["id"], version=released["version"])
        claimed = self.run_store("get", id=task["id"])["task"]
        self.run_store("task", session=other, id=task["id"], version=claimed["version"], title="Finished", status="done", notes="Verified")
        self.assertEqual(self.run_store("get", id=task["id"])["task"]["owner_session"], "")

    def test_linked_checkout_claims_and_legacy_tasks(self):
        legacy = self.run_store("task", title="Existing now", status="now", notes="", session="")
        self.assertEqual(self.run_store("get", id=legacy["id"])["task"]["owner_session"], "")
        linked = self.root / "linked-owner"
        (linked / ".jj").mkdir(parents=True)
        (linked / ".jj/repo").write_text("../../repo/.jj/repo")
        self.run_store("claim", root=linked, session="child", id=legacy["id"], version=1)
        record = self.run_store("board")["tasks"][0]
        self.assertEqual(record["owner_session"], "child")
        self.assertEqual(record["owner_root"], str(linked.resolve()))
        self.rejected("claim", root=self.other, session="child", id=legacy["id"], version=record["version"])
        self.rejected("message", session="", id=legacy["id"], body="Missing author")
        self.rejected("message", id=legacy["id"], body="bad\x1b[31m")
        self.rejected("claim", session="", id=legacy["id"], version=record["version"])
        active = self.run_store("task", title="New active", status="now", notes="", session="new-owner")
        self.assertEqual(self.run_store("get", id=active["id"])["task"]["owner_session"], "new-owner")
        self.rejected("release", session="source", id=legacy["id"], version=1, force=True)
        self.run_store("release", session="source", id=legacy["id"], version=record["version"], force=True)

    def test_notes_only_edits_preserve_claims_status_and_provenance(self):
        legacy = self.run_store("task", title="Existing work", status="now", notes="Unformatted", session="")
        self.run_store("notes", session="editor", id=legacy["id"], version=1, notes="## Scope\n\n- Existing facts.\n\n- More spacing.")
        record = self.run_store("get", id=legacy["id"])["task"]
        self.assertEqual(record["owner_session"], "", "formatting must not claim unowned Now tasks")
        self.assertEqual(record["status"], "now")
        self.assertEqual(record["session"], "")
        self.assertEqual(record["version"], 2)
        self.rejected("notes", id=legacy["id"], version=1, notes="Stale")
        self.run_store("claim", session="worker", id=legacy["id"], version=2)
        self.rejected("notes", session="editor", id=legacy["id"], version=3, notes="Foreign overwrite")
        self.run_store("notes", session="worker", id=legacy["id"], version=3, notes="- Existing facts.\n\n- More readable notes.")
        self.assertEqual(self.run_store("get", id=legacy["id"])["task"]["owner_session"], "worker")

    def test_closed_owner_cleanup_uses_native_tree_lock_and_preserves_work(self):
        data = self.root / "data"
        app = data / "yuke"
        locks = app / "yuke.db.owners"
        locks.mkdir(parents=True)
        (app / "yuke.db").touch()
        owner, tree = "1" * 32, "2" * 32
        lock = (locks / (tree + ".lock")).open("w+")
        self.addCleanup(lock.close)
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with patch.dict(os.environ, {"XDG_DATA_HOME": str(data), "YUKE_APPNAME": "yuke"}), self.inventory():
            first = self.run_store("task", session=owner, title="Live child work", status="now", notes="Keep the evidence")
            roots = {owner: tree}
            alive = self.run_store("presence", roots=roots)
            self.assertEqual(alive["states"][owner], "open")
            self.assertEqual(alive["released"], [])
            board = self.run_store("board")
            self.assertEqual(board["owner_counts"], {owner: 1})
            self.assertEqual(self.run_store("get", id=first["id"])["task"]["owner_session"], owner)
            fcntl.flock(lock, fcntl.LOCK_UN)
            viewed = self.run_store("presence", roots=roots, open_sessions=[tree])
            self.assertEqual(viewed["states"][owner], "open", "an open read-only chat must retain its assignment")
            self.assertEqual(viewed["released"], [])
            with patch.dict(os.environ, {"HERDR_ENV": "0"}):
                unavailable = self.run_store("presence", roots=roots)
                self.assertEqual(unavailable["states"][owner], "unknown", "no global inventory must not prove closure")
                self.assertEqual(unavailable["released"], [])
            reported = {"pane_id":"w1:p1", "agent_status":"unknown", "tokens":{"yuke_session_id":tree,"shortcut_number":"2"}}
            with self.inventory([reported]):
                self.assertEqual(self.run_store("presence", roots=roots)["states"][owner], "unknown", "an ambiguous pane report must not prove closure")
            with self.inventory([{**reported, "agent":"yuke"}]):
                self.assertEqual(self.run_store("presence", roots=roots)["states"][owner], "open", "a visible Yuke chat stays assigned even before its first run")
            transient = self.run_store("presence", roots=roots)
            self.assertEqual(transient["states"][owner], "closed")
            self.assertEqual(transient["released"], [], "one closed observation during reload must not release a claim")
            self.run_store("presence", roots=roots, open_sessions=[tree])
            restarted = self.run_store("presence", roots=roots)
            self.assertEqual(restarted["released"], [], "an open observation must reset the closure grace period")
            time.sleep(3.1)
            closed = self.run_store("presence", roots=roots)
            self.assertEqual(closed["states"][owner], "closed")
            self.assertEqual(len(closed["released"]), 1)
            detail = self.run_store("get", id=first["id"])
            self.assertEqual(detail["task"]["owner_session"], "")
            self.assertEqual(detail["task"]["status"], "now", "closure must not complete or defer work")
            self.assertEqual(detail["task"]["notes"], "Keep the evidence")
            self.assertEqual(detail["task"]["version"], first["version"] + 1)
            self.assertIn("closed", detail["messages"][-1]["body"])
            self.assertEqual(self.run_store("presence", roots=roots)["released"], [], "repeated cleanup must not add messages or versions")
            fresh = self.run_store("get", id=first["id"])["task"]
            newer_owner = "4" * 32
            self.run_store("claim", session=newer_owner, id=first["id"], version=fresh["version"])
            self.run_store("presence", roots=roots)
            self.assertEqual(self.run_store("get", id=first["id"])["task"]["owner_session"], newer_owner, "stale owner observations must not clear a newer owner")

    def test_unknown_lock_evidence_never_clears_assignments(self):
        data = self.root / "missing-data"
        owner = "3" * 32
        with patch.dict(os.environ, {"XDG_DATA_HOME": str(data), "YUKE_APPNAME": "yuke", "HERDR_ENV": "0"}):
            task = self.run_store("task", session=owner, title="Unknown presence", status="now", notes="")
            self.assertEqual(self.run_store("presence", roots={owner: owner})["states"][owner], "unknown")
            app = data / "yuke"
            locks = app / "yuke.db.owners"
            locks.mkdir(parents=True)
            (app / "yuke.db").touch()
            self.assertEqual(self.run_store("presence", roots={owner: owner})["states"][owner], "unknown")
            target = self.root / "foreign.lock"
            target.touch()
            (locks / (owner + ".lock")).symlink_to(target)
            self.assertEqual(self.run_store("presence", roots={owner: owner})["states"][owner], "unknown")
            self.assertEqual(self.run_store("get", id=task["id"])["task"]["owner_session"], owner)
            self.rejected("presence", roots={owner: "../../other"})

    def test_session_has_one_assignment_across_all_projects_and_write_paths(self):
        first = self.run_store("task", session="one-session", title="First assignment", status="now", notes="Keep")
        second = self.task()
        self.assertIn("unassign", self.rejected("claim", session="one-session", id=second["id"], version=1))
        self.assertIn("unassign", self.rejected("task", session="one-session", title="Another", status="now", notes=""))
        self.assertIn("unassign", self.rejected("task", root=self.other, session="one-session", title="Other project", status="now", notes=""))
        self.assertIn("unassign", self.rejected("task", session="one-session", id=second["id"], version=1, title="Second", status="now", notes=""))
        self.assertEqual(self.run_store("get", id=second["id"])["task"]["owner_session"], "")
        self.assertEqual(self.run_store("assigned", root=self.other, session="one-session")["tasks"][0]["id"], first["id"])
        self.assertEqual(self.run_store("assigned", session="one-session")["total"], 1)
        self.run_store("release", session="one-session", id=first["id"], version=1)
        self.run_store("claim", session="one-session", id=second["id"], version=1)
        self.run_store("task", session="one-session", id=second["id"], version=2, title="Finished", status="done", notes="Verified")
        self.assertEqual(self.run_store("assigned", session="one-session"), {"tasks": [], "total": 0})
        self.run_store("claim", session="one-session", id=first["id"], version=2)
        self.assertEqual(self.run_store("assigned", session="source")["total"], 0, "the creator is not the assigned session")

    def test_same_session_concurrent_claims_have_only_one_winner(self):
        tasks = [self.task(), self.task()]
        processes = [subprocess.Popen(self.command("claim", session="same-session", id=task["id"], version=1), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for task in tasks]
        results = [(process.communicate(), process.returncode) for process in processes]
        self.assertEqual(sorted(code for _, code in results), [0, 1])
        self.assertEqual(self.run_store("assigned", session="same-session")["total"], 1)

    def test_legacy_duplicate_assignments_are_reported_without_silent_reassignment(self):
        first = self.run_store("task", session="duplicate", title="Existing", status="now", notes="Keep")
        with sqlite3.connect(self.database) as db:
            for name, in db.execute("SELECT name FROM sqlite_master WHERE type='trigger'").fetchall():
                db.execute(f'DROP TRIGGER "{name}"')
            db.execute("INSERT INTO tasks SELECT 'old-duplicate', project, 'Old duplicate', status, notes, session, root, NULL, updated, version, github_url, owner_session, owner_root FROM tasks WHERE id=?", (first["id"],))
        snapshot = self.run_store("assigned", session="duplicate")
        self.assertEqual(snapshot["total"], 2)
        self.assertEqual({task["id"] for task in snapshot["tasks"]}, {first["id"], "old-duplicate"})
        self.run_store("notes", session="duplicate", id=first["id"], version=1, notes="Still editable")
        self.assertIn("unassign", self.rejected("task", session="duplicate", title="No third", status="now", notes=""))
        self.run_store("release", session="duplicate", id="old-duplicate", version=1)
        self.assertEqual(self.run_store("assigned", session="duplicate")["total"], 1)

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
