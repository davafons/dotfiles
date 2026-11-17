"""Check that davstack-sync merges upstream into local edits and renames for davstack."""
import importlib.machinery
import importlib.util
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "bin/davstack-sync"
loader = importlib.machinery.SourceFileLoader("davstack_sync", str(SCRIPT))
spec = importlib.util.spec_from_loader("davstack_sync", loader)
sync = importlib.util.module_from_spec(spec)
loader.exec_module(sync)


def tree(root, files):
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return root


class DavstackSync(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.ours = self.root / "davstack"
        self.ours.mkdir()
        sync.DAVSTACK = self.ours

    def merge(self, base, theirs, ours):
        tree(self.ours, ours)
        return sync.merge(tree(self.root / "base", base), tree(self.root / "theirs", theirs))

    def test_upstream_change_merges_around_a_local_edit(self):
        changed, conflicts, _ = self.merge(
            {"skills/a/SKILL.md": "one\ntwo\nthree\n"},
            {"skills/a/SKILL.md": "one\ntwo\nthree upstream\n"},
            {"skills/a/SKILL.md": "one local\ntwo\nthree\n"})
        self.assertEqual((self.ours / "skills/a/SKILL.md").read_text(), "one local\ntwo\nthree upstream\n")
        self.assertEqual((changed, conflicts), (["skills/a/SKILL.md"], []))

    def test_overlapping_edits_leave_conflict_markers(self):
        _, conflicts, _ = self.merge({"skills/a/SKILL.md": "x\n"}, {"skills/a/SKILL.md": "upstream\n"},
                                     {"skills/a/SKILL.md": "local\n"})
        self.assertEqual(conflicts, ["skills/a/SKILL.md"])
        self.assertIn("<<<<<<< davstack", (self.ours / "skills/a/SKILL.md").read_text())

    def test_additions_deletions_and_local_files(self):
        _, _, kept = self.merge(
            {"skills/gone/SKILL.md": "old\n", "skills/edited/SKILL.md": "old\n"},
            {"skills/new/SKILL.md": "new\n"},
            {"skills/gone/SKILL.md": "old\n", "skills/edited/SKILL.md": "mine\n", "skills/mine/SKILL.md": "mine\n"})
        self.assertEqual((self.ours / "skills/new/SKILL.md").read_text(), "new\n")
        self.assertFalse((self.ours / "skills/gone/SKILL.md").exists())
        self.assertEqual(kept, ["skills/edited/SKILL.md"])
        self.assertTrue((self.ours / "skills/mine/SKILL.md").exists())

    def test_transform_renames_and_adapts_for_linked_skills(self):
        root = tree(self.root / "upstream", {
            "skills/poteto-mode/SKILL.md": "See [adapter](../../docs/harness/claude-code.md). Type `/pstack:poteto-mode`.\n",
            "agents/poteto-agent.md": "---\nname: poteto-agent\nmodel: claude-opus-5-5-xhigh-fast\nis_background: true\n---\nUse pstack:poteto-agent.\n",
        })
        sync.transform(root)
        skill = (root / "skills/dav-mode/SKILL.md").read_text()
        self.assertIn(f"]({sync.DOCS}harness/claude-code.md)", skill)
        self.assertIn("`/dav-mode`", skill)
        self.assertEqual((root / "agents/dav-agent.md").read_text(), "---\nname: dav-agent\n---\nUse dav-agent.\n")


if __name__ == "__main__":
    unittest.main()
