"""Check global skill and agent links, without overwriting what the user owns."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
DAVSTACK = ROOT / "agents/.agents/davstack"
PERSONAL = ROOT / "agents/.agents/personal/skills"
AGENT_SKILLS = str(ROOT / "bin/bin/agent-skills")


def skill_names(root):
    return {p.name for p in root.iterdir() if (p / "SKILL.md").is_file()}


class AgentSkills(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)

    def run_command(self, command):
        return subprocess.run([AGENT_SKILLS, command], env={**os.environ, "HOME": str(self.home)},
                              capture_output=True, text=True, timeout=20)

    def test_link_installs_every_skill_and_agent_idempotently(self):
        for _ in range(2):
            result = self.run_command("link")
            self.assertEqual(result.returncode, 0, result.stderr)
        davstack = skill_names(DAVSTACK / "skills")
        self.assertIn("dav-mode", davstack)
        for harness in (".agents", ".claude"):
            self.assertEqual({p.name for p in (self.home / harness / "skills").iterdir()}, davstack | skill_names(PERSONAL))
            self.assertEqual((self.home / harness / "skills/dav-mode").resolve(), DAVSTACK / "skills/dav-mode")
        for name in ("dav-agent", "comment-sicko"):
            self.assertEqual((self.home / ".claude/agents" / f"{name}.md").resolve(), DAVSTACK / "agents" / f"{name}.md")

    def test_link_refuses_to_replace_a_user_agent(self):
        for kind in ("file", "link", "dangling"):
            with self.subTest(kind=kind):
                agent = self.home / ".claude/agents/dav-agent.md"
                agent.parent.mkdir(parents=True, exist_ok=True)
                agent.unlink(missing_ok=True)
                target = self.home / "user-agent"
                target.unlink(missing_ok=True)
                if kind == "file":
                    agent.write_text("user-owned agent")
                else:
                    if kind == "link":
                        target.write_text("user-owned agent")
                    agent.symlink_to(target)
                result = self.run_command("link")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("refusing to replace unmanaged agent", result.stderr)
                self.assertTrue(agent.is_symlink() or agent.read_text() == "user-owned agent")

    def test_link_refuses_to_replace_a_user_skill(self):
        skill = self.home / ".agents/skills/how/SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text("user-owned skill")
        result = self.run_command("link")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refusing to replace unmanaged", result.stderr)
        self.assertEqual(skill.read_text(), "user-owned skill")

    def test_link_removes_only_dangling_links_into_dotfiles(self):
        owned = self.home / ".claude/skills/removed-skill"
        owned.parent.mkdir(parents=True)
        owned.symlink_to(ROOT / "agents/.agents/davstack/skills/removed-skill")
        foreign = self.home / ".claude/skills/elsewhere"
        foreign.symlink_to(self.home / "missing")
        result = self.run_command("link")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(owned.is_symlink())
        self.assertTrue(foreign.is_symlink())

    def test_check_rejects_a_missing_agent(self):
        self.assertEqual(self.run_command("link").returncode, 0)
        agent = self.home / ".claude/agents/dav-agent.md"
        agent.unlink()
        result = self.run_command("check")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(f"missing or incorrect Claude agent link: {agent}", result.stderr)


if __name__ == "__main__":
    unittest.main()
