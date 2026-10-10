"""Check skill installation and preservation of user-owned files."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / "agents/.agents/davstack/skills"
SELECTED = ("how", "why", "teach", "recall", "create-verification-skill")
DAVSTACK = SELECTED + ("dav-mode", "blast-radius", "comment-sicko", "no-comments", "reflect", "tdd", "unslop", "technical-writing", "deslop", "loop", "figure-it-out")


class InvestigationSkills(unittest.TestCase):
    def link(self, home):
        return subprocess.run([str(ROOT / "bin/bin/agent-skills"), "link"], env={**os.environ, "HOME": str(home)}, capture_output=True, text=True, timeout=8)

    def test_isolated_install_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            for _ in range(2):
                result = self.link(home)
                self.assertEqual(result.returncode, 0, result.stderr)
            for harness in (".agents", ".claude"):
                for name in DAVSTACK:
                    link = home / harness / "skills" / name
                    self.assertTrue(link.is_symlink())
                    self.assertEqual(link.resolve(), SKILLS / name)
            self.assertEqual({p.name for p in (home / ".claude/skills").iterdir()}, set(DAVSTACK))
            self.assertFalse((home / ".agents/stacks").exists())
            self.assertFalse((home / ".claude/skills/poteto-mode").exists())

    def test_install_preserves_unmanaged_skill(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            directory = home / ".agents/skills/how"
            directory.mkdir(parents=True)
            skill = directory / "SKILL.md"
            skill.write_text("user-owned skill")
            result = self.link(home)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("refusing to replace unmanaged", result.stderr)
            self.assertEqual(skill.read_text(), "user-owned skill")


if __name__ == "__main__":
    unittest.main()
