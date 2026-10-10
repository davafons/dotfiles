"""Check that Shirabe's working stack has one portable, globally linked owner."""
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / "agents/.agents/skills"
MIGRATED = ("dav-mode", "blast-radius", "comment-sicko", "no-comments", "reflect", "tdd", "unslop", "figure-it-out")
INVESTIGATION = ("how", "why", "teach", "recall", "create-verification-skill")
PLAYBOOKS = {
    "agent-eval", "bug-fix", "encode", "feature", "forensics", "hillclimb", "investigate",
    "pause-safely", "perf", "plan", "prototype", "refactor", "session-pickup", "ship", "visual-parity", "write",
}


class DavstackMigration(unittest.TestCase):
    def test_migrated_skills_have_direct_sources(self):
        for name in MIGRATED:
            with self.subTest(skill=name):
                body = (SKILLS / name / "SKILL.md").read_text()
                self.assertTrue(body.startswith(f"---\nname: {name}\n"))
                self.assertIn("origin: shirabe", body)
                self.assertNotIn("## Here specifically", body)
                self.assertNotIn("docs/agents/", body.split("\n---\n", 1)[1])
                self.assertNotIn("bin/house-rules", body)
                self.assertNotIn("bin/brief", body)

    def test_every_playbook_is_routed_and_links_resolve(self):
        directory = SKILLS / "dav-mode/playbooks"
        self.assertEqual({p.stem for p in directory.glob("*.md")}, PLAYBOOKS)
        mode = (SKILLS / "dav-mode/SKILL.md").read_text()
        for name in PLAYBOOKS:
            self.assertIn(f"playbooks/{name}.md", mode)
        for name in MIGRATED:
            for path in (SKILLS / name).rglob("*.md"):
                for link in re.findall(r"\]\(([^)\s]+)\)", path.read_text()):
                    if "://" not in link and not link.startswith("#"):
                        self.assertTrue((path.parent / link.split("#")[0]).exists(), f"{path}: {link}")

    def test_common_rules_preserve_authority_and_encoding(self):
        rules = (SKILLS / "dav-mode/references/working-rules.md").read_text()
        for phrase in ("explicitly requests", "shared-desktop", "user's requested scope", "runtime check", "CI", "canonical helper"):
            self.assertIn(phrase, rules)
        self.assertIn(".jj/", rules)
        writing = (SKILLS / "unslop/references/writing.md").read_text()
        for mode in ("Tutorial", "How-to", "Reference", "Explanation"):
            self.assertIn(mode, writing)

    def test_comment_review_retains_constraint_until_encoded(self):
        for name in ("comment-sicko", "no-comments"):
            body = (SKILLS / name / "SKILL.md").read_text()
            self.assertIn("Report only" if name == "comment-sicko" else "comment-sicko/SKILL.md", body)
            self.assertIn("retain", body.lower())
        adapter = (SKILLS / "comment-sicko/agents/claude.md").read_text()
        self.assertIn("tools: Read, Grep, Glob", adapter)
        self.assertNotIn("Bash", adapter)
        self.assertIn("~/.agents/skills/comment-sicko/SKILL.md", adapter)

    def test_global_install_preserves_all_thirteen_skills(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            env = {**os.environ, "HOME": str(home)}
            for _ in range(2):
                result = subprocess.run([str(ROOT / "bin/bin/agent-skills"), "link"], env=env, capture_output=True, text=True, timeout=8)
                self.assertEqual(result.returncode, 0, result.stderr)
            names = set(MIGRATED + INVESTIGATION)
            for harness in (".agents", ".claude"):
                for name in names:
                    self.assertEqual((home / harness / "skills" / name).resolve(), SKILLS / name)
            self.assertEqual({p.name for p in (home / ".claude/skills").iterdir()}, names)
            self.assertEqual((home / ".claude/agents/comment-sicko.md").resolve(), SKILLS / "comment-sicko/agents/claude.md")

    def test_agent_install_does_not_overwrite_unmanaged_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            agent = home / ".claude/agents/comment-sicko.md"
            agent.parent.mkdir(parents=True)
            agent.write_text("user-owned agent")
            result = subprocess.run([str(ROOT / "bin/bin/agent-skills"), "link"], env={**os.environ, "HOME": str(home)}, capture_output=True, text=True, timeout=8)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(agent.read_text(), "user-owned agent")


if __name__ == "__main__":
    unittest.main()
