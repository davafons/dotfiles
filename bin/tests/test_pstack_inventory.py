"""Verify the reference inventory stays read-only and separates plugin layers."""
import importlib.machinery
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "bin/pstack-inventory"
loader = importlib.machinery.SourceFileLoader("pstack_inventory", str(SCRIPT))
spec = importlib.util.spec_from_loader(loader.name, loader)
module = importlib.util.module_from_spec(spec)
loader.exec_module(module)


class PstackInventory(unittest.TestCase):
    def test_inventory_separates_registered_and_dormant_skills(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            upstream, local = root / "upstream", root / "local"
            plugin = upstream / "pstack"
            manifest = plugin / ".cursor-plugin/plugin.json"
            manifest.parent.mkdir(parents=True)
            manifest.write_text(json.dumps({"version": "test"}))
            for name in ("how", "principle-proof"):
                path = plugin / "skills" / name / "SKILL.md"
                path.parent.mkdir(parents=True)
                path.write_text("upstream")
            for relative in ("skills/poteto-mode/playbooks/feature.md", "agents/reviewer.md",
                             "automations/demo/skills/triage/SKILL.md"):
                path = plugin / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("reference")
            (local / "how").mkdir(parents=True)
            (local / "how/SKILL.md").write_text("adapted")
            (local / "how/local.md").write_text("local")
            (plugin / "skills/how/upstream.md").write_text("upstream")
            (local / "how/shared.md").write_text("same")
            (plugin / "skills/how/shared.md").write_text("same")
            before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
            result = module.inventory(upstream, local)
            self.assertEqual(result["counts"], {"registered_skills": 2, "workflow_skills": 1, "principles": 1})
            self.assertEqual(result["workflow_skills"], ["how"])
            self.assertEqual(result["principles"], ["principle-proof"])
            self.assertEqual(result["playbooks"], ["feature"])
            self.assertEqual(result["agents"], ["reviewer"])
            self.assertEqual(result["dormant_automation_skills"], ["automations/demo/skills/triage/SKILL.md"])
            self.assertEqual(result["same_name_comparisons"]["how"], {
                "changed": ["SKILL.md"], "unchanged": ["shared.md"],
                "local_only": ["local.md"], "upstream_only": ["upstream.md"],
            })
            self.assertEqual({p: p.read_bytes() for p in root.rglob("*") if p.is_file()}, before)


if __name__ == "__main__":
    unittest.main()
