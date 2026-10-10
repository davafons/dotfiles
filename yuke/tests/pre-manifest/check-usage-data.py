#!/usr/bin/env python3
"""Exercise usage accounting against SQLite fixtures and optionally the real store."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest

sys.dont_write_bytecode = True
READER = Path(__file__).resolve().parents[1] / "plugins" / "usage-data.py"
SPEC = importlib.util.spec_from_file_location("usage_data", READER)
usage_data = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(usage_data)
NOW = datetime(2026, 10, 10, 12, tzinfo=timezone.utc)
SCHEMA = """
CREATE TABLE sessions (
 id BLOB PRIMARY KEY, root TEXT, origin TEXT, title TEXT, name TEXT, model TEXT,
 usage_input_total INTEGER DEFAULT 0, usage_output_total INTEGER DEFAULT 0,
 usage_reasoning_total INTEGER DEFAULT 0, usage_cache_read_total INTEGER DEFAULT 0,
 usage_cache_write_total INTEGER DEFAULT 0, cost_total REAL DEFAULT 0,
 cost_without_cache_total REAL DEFAULT 0, unpriced_count INTEGER DEFAULT 0,
 created_at_ms INTEGER, updated_at_ms INTEGER
);
CREATE TABLE events (session_id BLOB, seq INTEGER, name TEXT, payload TEXT, committed_at_ms INTEGER,
 PRIMARY KEY (session_id, seq));
CREATE TABLE session_configs (session_id BLOB, config_rev INTEGER, model TEXT, reasoning TEXT);
CREATE TABLE session_skills (session_id BLOB, name TEXT, path TEXT, canonical_path TEXT);
"""


def timestamp(day, hour=12):
    return int(datetime.fromisoformat(day + f"T{hour:02}:00:00+00:00").timestamp() * 1000)


def tool(name, arguments, state="completed", duration=10):
    return dict(type="tool", name=name, arguments=json.dumps(arguments),
                state=dict(type=state, duration_ms=duration, output="PRIVATE TOOL OUTPUT"))


class Fixture:
    def __init__(self, path):
        self.path = path
        self.db = sqlite3.connect(path)
        self.db.executescript(SCHEMA)
        self.seqs = {}
        self.message_ids = {}

    def session(self, index, root="/workspace/one", kind="root", model="provider/model"):
        sid = index.to_bytes(16, "big")
        self.db.execute("INSERT INTO sessions (id,root,origin,title,model,created_at_ms,updated_at_ms) VALUES (?,?,?,?,?,?,?)",
                        (sid, root, kind, "Fixture chat " + str(index), model, timestamp("2026-10-08"), timestamp("2026-10-10")))
        self.db.execute("INSERT INTO session_configs VALUES (?,?,?,?)", (sid, 0, model, "high"))
        self.seqs[sid] = self.message_ids[sid] = 0
        return sid

    def event(self, sid, name, payload, at=None):
        self.seqs[sid] += 1
        self.db.execute("INSERT INTO events VALUES (?,?,?,?,?)", (sid, self.seqs[sid], name, json.dumps(payload), at or timestamp("2026-10-10")))

    def message(self, sid, day="2026-10-10", role="assistant", tokens=None, cost=None, run=1, content=None, model=None, **extra):
        self.message_ids[sid] += 1
        message = dict(type=role, id=self.message_ids[sid], config_rev=0,
                       time=dict(created_at_ms=timestamp(day), completed_at_ms=timestamp(day) + 1000),
                       content=content or [dict(type="text", text="PRIVATE MESSAGE TEXT")], **extra)
        if role == "assistant":
            message["run_id"] = run
        if tokens is not None:
            message["tokens"] = dict(zip(usage_data.TOKEN_FIELDS, tokens))
            self.db.execute("""UPDATE sessions SET
                usage_input_total=usage_input_total+?, usage_output_total=usage_output_total+?,
                usage_reasoning_total=usage_reasoning_total+?, usage_cache_read_total=usage_cache_read_total+?,
                usage_cache_write_total=usage_cache_write_total+?, unpriced_count=unpriced_count+?
                WHERE id=?""", (*tokens, int(cost is None), sid))
        if cost is not None:
            message["cost"] = dict(total=cost[0], without_cache=cost[1])
            self.db.execute("UPDATE sessions SET cost_total=cost_total+?,cost_without_cache_total=cost_without_cache_total+? WHERE id=?", (*cost, sid))
        if model:
            message["provenance"] = dict(model=model, protocol="openai_responses")
        self.event(sid, "message.committed", message)

    def read(self, workspace=None):
        self.db.commit()
        return usage_data.snapshot(self.path, workspace, NOW)


class UsageDataTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="yuke-usage-data-")
        self.fixture = Fixture(Path(self.temp.name) / "yuke.db")

    def tearDown(self):
        self.fixture.db.close()
        self.temp.cleanup()

    def test_empty_history_and_missing_database(self):
        result = self.fixture.read()
        self.assertEqual(result["chats"], [])
        self.assertEqual(result["totals"]["input"], 0)
        self.assertEqual(result["currentStreak"], 0)
        missing = Path(self.temp.name) / "missing.db"
        with self.assertRaises(sqlite3.OperationalError):
            usage_data.snapshot(missing)
        self.assertFalse(missing.exists())

    def test_subsets_children_and_model_changes_are_not_double_counted(self):
        root = self.fixture.session(1)
        child = self.fixture.session(2, kind="child")
        self.fixture.message(root, tokens=(100, 20, 10, 80, 5), cost=(0.5, 2), finish="stop")
        self.fixture.message(child, tokens=(30, 10, 4, 20, 0), cost=(0.1, 0.5), model="another/changed", finish="tool_calls")
        result = self.fixture.read()
        totals = result["totals"]
        self.assertEqual(totals["input"] + totals["output"], 160)
        self.assertEqual(totals["reasoning"], 14)
        self.assertEqual(totals["cache_read"], 100)
        self.assertAlmostEqual(totals["cost"], 0.6)
        self.assertAlmostEqual(totals["withoutCache"] - totals["cost"], 1.9)
        self.assertEqual((result["chatCount"], result["childCount"]), (1, 1))
        self.assertEqual({row["name"] for row in result["models"]}, {"provider/model", "another/changed"})
        self.assertEqual({row["name"] for row in result["providers"]}, {"provider", "another"})
        self.assertEqual(sum(row["input"] for row in result["daily"]), totals["input"])
        self.assertEqual(result["notes"], [])

    def test_unknown_prices_and_absent_tokens_are_distinct(self):
        sid = self.fixture.session(1)
        self.fixture.message(sid, tokens=(10, 2, 0, 0, 0))
        self.fixture.message(sid)
        result = self.fixture.read()
        self.assertEqual(result["totals"]["unpriced"], 1)
        self.assertEqual(result["totals"]["unreported"], 1)
        self.assertEqual(result["totals"]["messages"], 2)
        self.assertEqual(result["models"][0]["unpriced"], 1)
        self.assertEqual(result["daily"][0]["unreported"], 1)

    def test_workspace_is_exact_parameterized_and_includes_its_children(self):
        root = self.fixture.session(1)
        child = self.fixture.session(2, kind="child")
        other = self.fixture.session(3, root="/workspace/one-more")
        for sid in (root, child, other):
            self.fixture.message(sid, tokens=(10, 5, 0, 0, 0), cost=(0, 0))
        result = self.fixture.read("/workspace/one")
        self.assertEqual(len(result["chats"]), 2)
        self.assertEqual(result["totals"]["input"], 20)
        self.assertEqual(self.fixture.read("' OR 1=1 --")["chats"], [])

    def test_streak_today_yesterday_gaps_and_local_timezone(self):
        sid = self.fixture.session(1)
        for day in ["2026-10-03", "2026-10-04", "2026-10-05", "2026-10-08", "2026-10-09"]:
            self.fixture.message(sid, day=day, tokens=(1, 1, 0, 0, 0), cost=(0, 0))
        result = self.fixture.read()
        self.assertEqual((result["currentStreak"], result["longestStreak"]), (2, 3))
        self.fixture.message(sid, tokens=(1, 1, 0, 0, 0), cost=(0, 0))
        result = self.fixture.read()
        self.assertEqual(result["currentStreak"], 3)
        old_tz = os.environ.get("TZ")
        try:
            os.environ["TZ"] = "Pacific/Honolulu"
            time.tzset()
            self.fixture.message(sid, day="2026-10-01", tokens=(3, 1, 0, 0, 0), cost=(0, 0))
            self.fixture.db.execute("UPDATE events SET payload=json_set(payload,'$.time.created_at_ms',?) WHERE session_id=? AND seq=?", (timestamp("2026-10-01", 2), sid, self.fixture.seqs[sid]))
            self.assertEqual(self.fixture.read()["daily"][0]["date"], "2026-09-30")
        finally:
            if old_tz is None:
                os.environ.pop("TZ", None)
            else:
                os.environ["TZ"] = old_tz
            time.tzset()

    def test_tool_failures_and_skill_observations_are_deduplicated_per_run(self):
        sid = self.fixture.session(1)
        self.fixture.db.execute("INSERT INTO session_skills VALUES (?,?,?,?)", (sid, "test-skill", "/workspace/one/.agents/skills/test/SKILL.md", "/actual/test/SKILL.md"))
        self.fixture.message(sid, role="user", skill_name="test-skill")
        self.fixture.event(sid, "run.started", dict(run_id=1))
        parts = [tool("read", {"path": ".agents/skills/test/SKILL.md"}),
                 tool("read", {"path": "/actual/test/SKILL.md"}),
                 tool("read", {"path": "/actual/test/SKILL.md"}, state="error"),
                 tool("exec", {"command": "false"}, state="error"),
                 tool("exec", {"command": "sleep 10"}, state="canceled"),
                 tool("skill", {"name": "test-skill"}), tool("read", [])]
        self.fixture.message(sid, tokens=(10, 1, 0, 0, 0), cost=(0, 0), content=parts)
        self.fixture.message(sid, run=2, tokens=(10, 1, 0, 0, 0), cost=(0, 0), content=[tool("read", {"path": "/actual/test/SKILL.md"})])
        result = self.fixture.read()
        self.assertEqual(result["skills"], [dict(name="test-skill", uses=2, invocations=2, reads=3)])
        tools = {row["name"]: row for row in result["tools"]}
        self.assertEqual(tools["exec"]["errors"], 1)
        self.assertEqual(tools["exec"]["canceled"], 1)
        self.assertEqual(result["totals"]["tools"], 8)
        self.assertEqual(result["daily"][0]["tools"], 8)
        self.assertNotIn("PRIVATE", json.dumps(result))

    def test_multiple_native_skills_count_once_per_run_including_steering(self):
        sid = self.fixture.session(1)
        self.fixture.message(sid, role="user", skill_names=["alpha", "beta"])
        self.fixture.event(sid, "run.started", dict(run_id=1))
        self.fixture.message(sid, role="user", skill_names=["alpha", "beta"])
        self.fixture.event(sid, "run.done", dict(timing=dict(started_at_ms=1, ended_at_ms=2), outcome=dict(type="turn")))
        self.fixture.message(sid, role="user", skill_name="alpha")
        self.fixture.event(sid, "run.started", dict(run_id=2))
        self.fixture.message(sid, role="user", skill_names=["alpha"])
        self.fixture.message(sid, role="user", content=[dict(type="text", text='<skill_content name="not-native">literal</skill_content>')])
        self.assertEqual(self.fixture.read()["skills"], [
            dict(name="alpha", uses=2, invocations=4, reads=0),
            dict(name="beta", uses=1, invocations=2, reads=0),
        ])

    def test_chat_elapsed_and_active_run_time_have_different_meanings(self):
        sid = self.fixture.session(1)
        self.fixture.message(sid, day="2026-10-08", role="user")
        self.fixture.message(sid, day="2026-10-10", tokens=(1, 1, 0, 0, 0), cost=(0, 0), finish="stop")
        self.fixture.event(sid, "run.done", dict(timing=dict(started_at_ms=100, ended_at_ms=25100), outcome=dict(type="turn")))
        result = self.fixture.read()
        self.assertEqual(result["longestChatMs"], 2 * 86400000 + 1000)
        self.assertEqual(result["activeMs"], 25000)
        self.assertEqual(result["outcomes"], {"turn": 1})
        self.assertEqual(result["roles"], {"user": 1, "assistant": 1})

    def test_lifetime_summary_does_not_silently_drop_missing_event_history(self):
        sid = self.fixture.session(1)
        self.fixture.message(sid, tokens=(10, 1, 0, 0, 0), cost=(0, 0))
        self.fixture.db.execute("UPDATE sessions SET usage_input_total=100 WHERE id=?", (sid,))
        result = self.fixture.read()
        self.assertEqual(result["totals"]["input"], 100)
        self.assertEqual(result["daily"][0]["input"], 10)
        self.assertIn("retained events", result["notes"][0])

    def test_read_only_snapshot_and_private_output_larger_than_exec_limit(self):
        for i in range(1, 301):
            self.fixture.session(i)
        self.fixture.db.commit()
        before = hashlib.sha256(Path(self.fixture.path).read_bytes()).digest()
        output = Path(self.temp.name) / "cache" / "usage.json"
        process = subprocess.run(["python3", str(READER), str(self.fixture.path), "--output", str(output)], capture_output=True, text=True)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(process.stdout, "")
        self.assertGreater(output.stat().st_size, 65536)
        self.assertEqual(output.stat().st_mode & 0o777, 0o600)
        self.assertEqual(len(json.loads(output.read_text())["chats"]), 300)
        self.assertEqual(before, hashlib.sha256(Path(self.fixture.path).read_bytes()).digest())


def check_real(database):
    db = sqlite3.connect(Path(database).resolve().as_uri() + "?mode=ro", uri=True)
    try:
        # A backup gives both queries the same WAL snapshot without touching the source.
        with tempfile.TemporaryDirectory(prefix="yuke-usage-real-") as directory:
            copy = Path(directory) / "yuke.db"
            target = sqlite3.connect(copy)
            db.backup(target)
            expected = target.execute("SELECT sum(usage_input_total),sum(usage_output_total),sum(cost_total),count(*) FROM sessions").fetchone()
            target.close()
            result = usage_data.snapshot(copy)
            assert result["totals"]["input"] == (expected[0] or 0)
            assert result["totals"]["output"] == (expected[1] or 0)
            assert abs(result["totals"]["cost"] - (expected[2] or 0)) < 1e-8
            assert len(result["chats"]) == expected[3]
            for workspace in {chat["root"] for chat in result["chats"]}:
                scoped = usage_data.snapshot(copy, workspace)
                assert all(chat["root"] == workspace for chat in scoped["chats"])
                assert scoped["totals"]["input"] == sum(chat["input"] for chat in result["chats"] if chat["root"] == workspace)
            print("Real store verified:", expected[3], "sessions;", result["totals"]["input"] + result["totals"]["output"], "tokens; cost and workspace totals match SQLite")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--real", type=Path)
    args = parser.parse_args()
    previous_tz = os.environ.get("TZ")
    os.environ["TZ"] = "UTC"
    time.tzset()
    try:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(UsageDataTest)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        if not result.wasSuccessful():
            raise SystemExit(1)
        if args.real:
            check_real(args.real)
    finally:
        if previous_tz is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = previous_tz
        time.tzset()
