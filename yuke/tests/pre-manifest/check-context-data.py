#!/usr/bin/env python3
"""Pin read-only, byte-based attribution and stale-budget behavior."""
import importlib.util
from pathlib import Path
import sqlite3
import tempfile
import unittest

HELPER = Path(__file__).resolve().parents[1] / "plugins/context-data.py"
spec = importlib.util.spec_from_file_location("context_data", HELPER)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ContextDataTest(unittest.TestCase):
    def test_snapshot_is_read_only_and_stale_overhead_stays_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.sqlite"
            db = sqlite3.connect(path)
            db.executescript("""
                CREATE TABLE sessions(id BLOB, model TEXT, prompt_tokens INTEGER);
                CREATE TABLE session_prompts(session_id BLOB, generation INTEGER);
                CREATE TABLE session_prompt_sections(session_id BLOB, position INTEGER, key TEXT, text TEXT);
                CREATE TABLE session_instructions(session_id BLOB, scope TEXT, path TEXT);
                CREATE TABLE session_skills(session_id BLOB, name TEXT, scope TEXT, description TEXT);
                CREATE TABLE messages(session_id BLOB, message_id INTEGER, role TEXT, model TEXT);
            """)
            sid = bytes.fromhex("01" * 16)
            db.execute("INSERT INTO sessions VALUES (?,?,?)", (sid, "test/model", 100))
            db.execute("INSERT INTO session_prompts VALUES (?,?)", (sid, 3))
            db.execute("INSERT INTO messages VALUES (?,?,?,?)", (sid, 1, "assistant", "test/model"))
            for index, (key, text) in enumerate([("base", "あ"), ("empty", ""), ("skills", "abcde")]):
                db.execute("INSERT INTO session_prompt_sections VALUES (?,?,?,?)", (sid, index, key, text))
            db.execute("INSERT INTO session_skills VALUES (?,?,?,?)", (sid, "demo", "workspace", "Private body is not loaded"))
            db.commit()
            before = path.read_bytes()
            result = module.snapshot(path, sid.hex())
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(result["system"], 3)
            self.assertEqual(sum(section["tokens"] for section in result["sections"]), 3)
            self.assertEqual(result["tools"], 97)
            self.assertEqual(result["sections"][0]["bytes"], 3)
            self.assertNotIn("text", result["sections"][0])
            db.execute("UPDATE sessions SET model='test/other'")
            db.commit()
            self.assertIsNone(module.snapshot(path, sid.hex())["tools"])
            db.execute("UPDATE sessions SET model='test/model'")
            db.execute("UPDATE session_prompts SET generation=0")
            db.commit()
            self.assertIsNone(module.snapshot(path, sid.hex())["tools"])
            stale = module.snapshot(path, sid.hex())
            self.assertTrue(stale["promptAvailable"])
            self.assertTrue(stale["stale"])
            catalog = "Catalog header\n\n<available_skills>\n  <skill>\n    <name>demo</name>\n    <description>あ &amp; example</description>\n    <location>/demo/SKILL.md</location>\n  </skill>\n</available_skills>"
            db.execute("UPDATE session_prompt_sections SET text=? WHERE key='skills'", (catalog,))
            db.commit()
            result = module.snapshot(path, sid.hex())
            section = next(row for row in result["sections"] if row["key"] == "skills")
            self.assertEqual(sum(row["tokens"] or 0 for row in result["skills"]) + result["skillOverhead"]["tokens"], section["tokens"])
            self.assertEqual(sum(row["bytes"] or 0 for row in result["skills"]) + result["skillOverhead"]["bytes"], section["bytes"])
            self.assertGreater(result["skills"][0]["tokens"], 0)
            db.execute("UPDATE session_prompt_sections SET text='No catalog in this custom prompt' WHERE key='skills'")
            db.commit()
            self.assertIsNone(module.snapshot(path, sid.hex())["skills"][0]["tokens"])
            db.execute("UPDATE session_prompts SET generation=4")
            db.execute("UPDATE sessions SET prompt_tokens=1")
            db.commit()
            self.assertFalse(module.snapshot(path, sid.hex())["valid"])
            with self.assertRaises(ValueError):
                module.snapshot(path, "02" * 16)
            db.close()


if __name__ == "__main__":
    unittest.main()
