"""Check global skill and agent installation without overwriting user files."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / "agents/.agents/davstack/skills"
MIGRATED = ("dav-mode", "blast-radius", "comment-sicko", "no-comments", "reflect", "tdd", "unslop", "technical-writing", "deslop", "loop", "figure-it-out", "benchmark-checklist", "show-me-your-work")
INVESTIGATION = ("how", "why", "teach", "recall", "create-verification-skill")


class DavstackMigration(unittest.TestCase):
    def test_global_install_preserves_all_skills(self):
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
            for harness, filename in ((".claude", "claude.md"), (".codex", "codex.toml")):
                extension = Path(filename).suffix
                agent = home / harness / "agents" / f"comment-sicko{extension}"
                self.assertTrue(agent.is_symlink())
                self.assertEqual(agent.resolve(), SKILLS / "comment-sicko/agents" / filename)

    def test_dav_agent_install_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            env = {**os.environ, "HOME": str(home)}
            for _ in range(2):
                result = subprocess.run([str(ROOT / "bin/bin/agent-skills"), "link"], env=env, capture_output=True, text=True, timeout=8)
                self.assertEqual(result.returncode, 0, result.stderr)
            for harness, filename in ((".claude", "claude.md"), (".codex", "codex.toml")):
                agent = home / harness / "agents" / f"dav-agent{Path(filename).suffix}"
                self.assertTrue(agent.is_symlink())
                self.assertEqual(agent.resolve(), SKILLS / "dav-mode/agents" / filename)

    def test_dav_agent_install_preserves_user_files_and_links(self):
        for harness, extension in ((".claude", ".md"), (".codex", ".toml")):
            for kind in ("file", "link", "dangling"):
                with self.subTest(harness=harness, kind=kind), tempfile.TemporaryDirectory() as temporary:
                    home = Path(temporary)
                    agent = home / harness / "agents" / f"dav-agent{extension}"
                    agent.parent.mkdir(parents=True)
                    target = home / "owned-agent"
                    if kind == "file":
                        agent.write_text("user-owned agent")
                    else:
                        if kind == "link":
                            target.write_text("user-owned agent")
                        agent.symlink_to(target)
                    result = subprocess.run([str(ROOT / "bin/bin/agent-skills"), "link"], env={**os.environ, "HOME": str(home)}, capture_output=True, text=True, timeout=8)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("refusing to replace unmanaged agent", result.stderr)
                    if kind == "file":
                        self.assertEqual(agent.read_text(), "user-owned agent")
                    else:
                        self.assertEqual(agent.readlink(), target)

    def test_check_rejects_a_missing_dav_agent(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            env = {**os.environ, "HOME": str(home)}
            command = [str(ROOT / "bin/bin/agent-skills")]
            installed = subprocess.run(command + ["link"], env=env, capture_output=True, text=True, timeout=8)
            self.assertEqual(installed.returncode, 0, installed.stderr)
            agent = home / ".codex/agents/dav-agent.toml"
            agent.unlink(missing_ok=True)
            result = subprocess.run(command + ["check"], env=env, capture_output=True, text=True, timeout=8)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(f"missing or incorrect Codex agent link: {agent}", result.stderr)

    def test_agent_install_does_not_overwrite_unmanaged_file(self):
        for harness, extension in ((".claude", ".md"), (".codex", ".toml")):
            with self.subTest(harness=harness), tempfile.TemporaryDirectory() as temporary:
                home = Path(temporary)
                agent = home / harness / "agents" / f"comment-sicko{extension}"
                agent.parent.mkdir(parents=True)
                agent.write_text("user-owned agent")
                result = subprocess.run([str(ROOT / "bin/bin/agent-skills"), "link"], env={**os.environ, "HOME": str(home)}, capture_output=True, text=True, timeout=8)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("refusing to replace unmanaged agent", result.stderr)
                self.assertEqual(agent.read_text(), "user-owned agent")

    def test_agent_install_preserves_unrelated_links(self):
        for harness, extension in ((".claude", ".md"), (".codex", ".toml")):
            for dangling in (False, True):
                with self.subTest(harness=harness, dangling=dangling), tempfile.TemporaryDirectory() as temporary:
                    home = Path(temporary)
                    target = home / "user-agent"
                    if not dangling:
                        target.write_text("user-owned agent")
                    agent = home / harness / "agents" / f"comment-sicko{extension}"
                    agent.parent.mkdir(parents=True)
                    agent.symlink_to(target)
                    result = subprocess.run([str(ROOT / "bin/bin/agent-skills"), "link"], env={**os.environ, "HOME": str(home)}, capture_output=True, text=True, timeout=8)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(agent.readlink(), target)
                    if not dangling:
                        self.assertEqual(target.read_text(), "user-owned agent")

    def test_owned_claude_agent_link_is_migrated(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            agent = home / ".claude/agents/comment-sicko.md"
            agent.parent.mkdir(parents=True)
            agent.symlink_to(ROOT / "agents/.agents/skills/comment-sicko/agents/claude.md")
            result = subprocess.run([str(ROOT / "bin/bin/agent-skills"), "link"], env={**os.environ, "HOME": str(home)}, capture_output=True, text=True, timeout=8)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(agent.resolve(), SKILLS / "comment-sicko/agents/claude.md")
            self.assertEqual((home / ".codex/agents/comment-sicko.toml").resolve(), SKILLS / "comment-sicko/agents/codex.toml")

    def test_check_rejects_missing_or_incorrect_codex_agent(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            env = {**os.environ, "HOME": str(home)}
            command = [str(ROOT / "bin/bin/agent-skills")]
            installed = subprocess.run(command + ["link"], env=env, capture_output=True, text=True, timeout=8)
            self.assertEqual(installed.returncode, 0, installed.stderr)
            agent = home / ".codex/agents/comment-sicko.toml"
            agent.parent.mkdir(parents=True, exist_ok=True)
            for wrong_target in (False, True):
                with self.subTest(wrong_target=wrong_target):
                    agent.unlink(missing_ok=True)
                    if wrong_target:
                        agent.symlink_to(SKILLS / "comment-sicko/agents/claude.md")
                    result = subprocess.run(command + ["check"], env=env, capture_output=True, text=True, timeout=8)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(f"missing or incorrect Codex agent link: {agent}", result.stderr)


if __name__ == "__main__":
    unittest.main()
