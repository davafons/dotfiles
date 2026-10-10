#!/usr/bin/env python3
"""Check index replacement, incomplete history, scoped retrieval, and bounded file search."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

HELPER = Path(__file__).resolve().parents[1] / "plugins/search-store.py"
spec = importlib.util.spec_from_file_location("search_store", HELPER)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SearchStoreTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="yuke-search-store-")
        self.root = Path(self.temp.name).resolve()
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        self.database = self.root / "cache/history.db"
        self.store = module.Store(self.database)
        self.items = [dict(id="local", title="Ownership review", root=str(self.workspace), signature="1:2", updated=1),
                      dict(id="other", title="Other design", root="/other", signature="2:1", updated=2)]
        self.store.manifest(self.items)

    def tearDown(self):
        self.store.db.close()
        self.temp.cleanup()

    def index(self, sid, body, signature="1:2"):
        self.store.begin(sid)
        for chunk in (body[:4], body[4:]):
            self.store.part(dict(session_id=sid, message_id=8, part_id=0, role="assistant", body=chunk))
        self.store.finish(sid, signature)

    def chats(self, query, root=None):
        return [item for item in self.store.search(query, "chats", root)["items"] if item["kind"] == "chat"]

    def test_history_replacement_deletion_and_reopen(self):
        self.index("local", "Ownership locks protect the 🐈 session.")
        hit = self.chats("ownership lock", str(self.workspace))[0]
        self.assertEqual(self.store.preview(hit, None)["text"], "Ownership locks protect the 🐈 session.")
        self.assertEqual(self.chats("ownership", "/other"), [])
        self.index("other", "Ownership in another workspace", "2:1")
        self.assertEqual({item["session_id"] for item in self.chats("ownership")}, {"local", "other"})
        self.store.db.close()
        self.store = module.Store(self.database)
        self.assertEqual(self.store.manifest(self.items)["dirty"], [])
        self.items[0]["signature"] = "3:1"
        self.assertEqual(self.store.manifest(self.items)["dirty"], ["local"])
        self.assertEqual(self.chats("ownership", str(self.workspace)), [])
        self.index("local", "A replacement answer", "3:1")
        self.assertEqual(len(self.chats("replacement")), 1)
        self.store.manifest(self.items[1:])
        self.assertEqual(self.chats("replacement"), [])
        self.assertEqual(self.database.stat().st_mode & 0o777, 0o600)

    def test_partial_manifest_refresh_preserves_other_chats(self):
        self.index("other", "A stable cobalt answer", "2:1")
        latest = dict(self.items[0], signature="5:3")
        self.store.dispatch({"action": "manifest", "items": [latest], "partial": True})
        self.assertEqual(len(self.chats("cobalt")), 1)
        self.index("local", "A newly committed sapphire answer", "5:3")
        self.assertEqual(len(self.chats("sapphire")), 1)

    def test_partial_history_never_becomes_a_ready_index(self):
        self.store.begin("local")
        self.store.part(dict(session_id="local", message_id=8, part_id=0, role="user", body="incomplete answer"))
        self.assertEqual(self.chats("incomplete"), [])
        self.store.db.close()
        self.store = module.Store(self.database)
        self.assertIn("local", self.store.manifest(self.items)["dirty"])
        self.index("local", "complete answer")
        self.assertEqual(len(self.chats("complete")), 1)
        self.assertEqual(self.chats("incomplete"), [])

    def test_stale_writer_cannot_replace_newer_history(self):
        self.store.begin("local")
        self.store.part(dict(session_id="local", message_id=8, part_id=0, role="user", body="stale answer"))
        other = module.Store(self.database)
        try:
            updated = [dict(self.items[0], signature="4:1"), self.items[1]]
            other.manifest(updated)
            with self.assertRaisesRegex(RuntimeError, "changed during indexing"):
                self.store.finish("local", "1:2")
        finally:
            other.db.close()
        self.assertEqual(self.chats("stale"), [])

    def test_file_search_ignores_exclusions_and_does_not_run_query(self):
        (self.workspace / ".ignore").write_text("private.txt\n")
        (self.workspace / "private.txt").write_text("needle secret\n")
        (self.workspace / "public space.txt").write_text("needle visible\n" * 90)
        (self.workspace / "binary.bin").write_bytes(b"\0needle hidden")
        result = self.store.search("needle", "files", str(self.workspace))
        self.assertEqual(len(result["items"]), 40)
        self.assertIn("capped", result["note"])
        self.assertEqual({item["path"] for item in result["items"]}, {"public space.txt"})
        self.assertIn("> 1", self.store.preview(result["items"][0], str(self.workspace))["text"])
        self.assertEqual(self.store.search("$(touch hacked)", "files", str(self.workspace))["items"], [])
        self.assertFalse((self.workspace / "hacked").exists())
        paths = self.store.search("ps", "files", str(self.workspace))
        self.assertEqual(paths["items"][0]["path"], "public space.txt")
        (self.workspace / "new.txt").write_text("new content")
        self.store.manifest(self.items)
        self.assertEqual(self.store.search("new", "files", str(self.workspace))["items"][0]["path"], "new.txt")

    def test_large_passage_preview_keeps_the_match(self):
        self.index("local", "start " + "padding " * 10000 + "rareword lives here")
        hit = self.chats("rareword")[0]
        preview = self.store.preview(hit, None, "rareword")
        self.assertIn("rareword lives here", preview["text"][:8000])
        self.assertIn("passage", preview["note"])
        self.assertLessEqual(len(preview["text"]), 4000)
        self.index("local", "x" * 32000 + " rareword lives here")
        hit = self.chats("rareword")[0]
        preview = self.store.preview(hit, None, "rareword")
        self.assertIn("rareword lives here", preview["text"][:8000])
        self.assertLessEqual(len(preview["text"]), 4000)
        result = self.store.search(" ".join(["rareword"] * 17), "chats", None)
        self.assertEqual(result["items"], [])
        self.assertIn("16 words", result["note"])

    def test_preview_highlights_the_words_fts_actually_matches(self):
        self.index("local", "A café owns these ownership locks.")
        hit = self.chats("cafe owner")[0]
        preview = self.store.preview(hit, None, "cafe owner")
        self.assertIn("café", preview.get("matches", []))
        self.assertIn("ownership", preview.get("matches", []))
        self.assertEqual(preview["text"], "A café owns these ownership locks.")

    def test_preview_refuses_outside_paths_and_long_lines(self):
        outside = self.root / "outside.txt"
        outside.write_text("private")
        (self.workspace / "link.txt").symlink_to(outside)
        item = dict(kind="file", path="link.txt", line=1)
        with self.assertRaisesRegex(RuntimeError, "cannot leave"):
            self.store.preview(item, str(self.workspace))
        item["path"] = "../outside.txt"
        with self.assertRaisesRegex(RuntimeError, "cannot leave"):
            self.store.preview(item, str(self.workspace))
        (self.workspace / "long.txt").write_text("x" * 20000)
        item["path"] = "long.txt"
        with self.assertRaisesRegex(RuntimeError, "16 KiB"):
            self.store.preview(item, str(self.workspace))


if __name__ == "__main__":
    unittest.main()
