"""Check davstack's five selected skills and their installation."""
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / "agents/.agents/skills"
SELECTED = ("how", "why", "teach", "recall", "create-verification-skill")
DAVSTACK = SELECTED + ("dav-mode", "blast-radius", "comment-sicko", "no-comments", "reflect", "tdd", "unslop", "figure-it-out")
REVISION = "d73344bee8cf22e53b9d5f4cf5749d38ba38c174"


class InvestigationSkills(unittest.TestCase):
    def test_selected_skills_have_provenance_and_license(self):
        for name in SELECTED:
            with self.subTest(skill=name):
                directory = SKILLS / name
                body = (directory / "SKILL.md").read_text()
                self.assertTrue(body.startswith(f"---\nname: {name}\n"))
                self.assertIn("\ndescription: ", body)
                self.assertIn(f"revision: {REVISION}", body)
                self.assertIn(f"/pstack/skills/{name}", body)
                self.assertIn("license: MIT", body)
                self.assertNotIn("disable-model-invocation:", body)
                self.assertIn("Copyright (c) 2026 Lauren Tan", (directory / "LICENSE").read_text())
                self.assertIn("## Runtime adaptation", body)

    def test_local_markdown_links_resolve(self):
        for name in SELECTED:
            for path in (SKILLS / name).rglob("*.md"):
                for link in re.findall(r"\]\(([^)\s]+)\)", path.read_text()):
                    if "://" in link or link.startswith("#") or "{" in link:
                        continue
                    if link == "url" and path.name == "synthesizer-prompt.md":
                        continue  # Upstream's illustrative citation placeholder.
                    target = path.parent / link.split("#")[0]
                    self.assertTrue(target.exists(), f"{path}: {link}")

    def test_how_and_why_reference_contracts(self):
        how = SKILLS / "how/references"
        for name in ("explorer-prompt.md", "explainer-prompt.md"):
            self.assertTrue((how / name).is_file())
        why = SKILLS / "why/references"
        confidence = (why / "epistemics.md").read_text()
        for tier in ("Direct", "Supported", "Inferred", "Speculative", "Unknown"):
            self.assertIn(tier, confidence)
        sources = {p.stem for p in (why / "sources").glob("*.md")}
        self.assertEqual(sources, {"code-archaeology", "linear", "notion", "slack", "datadog", "sentry", "databricks", "incident-postmortem"})
        body = (SKILLS / "why/SKILL.md").read_text()
        self.assertIn("All\ninvestigation is read-only", body)
        self.assertIn("jj log --no-graph --patch --git <file>", body)
        self.assertIn("Record unavailable sources as gaps", body)

    def test_teach_and_recall_do_not_require_unimported_skills(self):
        teach = (SKILLS / "teach/SKILL.md").read_text()
        self.assertIn("Run them serially unless the user", teach)
        self.assertIn("[unslop](../unslop/SKILL.md)", teach)
        recall = (SKILLS / "recall/SKILL.md").read_text()
        self.assertIn("Never search unrelated", recall)
        self.assertIn("not recovered history", recall)
        self.assertIn("[verified, working copy]", recall)

    def test_verification_generation_contract(self):
        directory = SKILLS / "create-verification-skill"
        body = (directory / "SKILL.md").read_text()
        self.assertIn(".agents/skills/verify-<app>/SKILL.md", body)
        self.assertNotIn(".cursor/skills/verify-<app>/", body)
        for section in ("Launch", "Doctor", "Drive", "Evidence", "Cleanup", "Helpers"):
            self.assertIn(f"**{section}:**", body)
        self.assertIn("A generated skill that was never executed is a draft", body)
        self.assertIn("Do not call it verified", body)
        self.assertIn("Native GUI activation or system-wide input requires explicit permission", body)
        examples = directory / "references/feature-map-example"
        self.assertEqual({p.name for p in examples.iterdir()}, {"README.md", "create-note.md", "search.md"})
        for name in ("create-note.md", "search.md"):
            headings = re.findall(r"^## (.+)$", (examples / name).read_text(), re.M)
            self.assertEqual(headings, ["Sub-features", "How to get to it (user POV)", "Driving it with control-notes", "Gotchas"])

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
