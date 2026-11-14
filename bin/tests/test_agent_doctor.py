import importlib.machinery
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


loader = importlib.machinery.SourceFileLoader("agent_doctor", str(Path(__file__).parents[1] / "bin/agent-doctor"))
spec = importlib.util.spec_from_loader(loader.name, loader)
doctor = importlib.util.module_from_spec(spec)
loader.exec_module(doctor)


class AgentDoctorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.home, self.dotfiles = root / "home", root / "dotfiles"
        self.manifest = self.dotfiles / "agents/.mcporter/mcporter.json"
        self.write(self.manifest, json.dumps({"mcpServers": {"grafana": {"command": "codex-mcp-grafana", "env": {"GRAFANA_URL": "http://monitoring:3010"}}}}))
        self.write(self.dotfiles / "codex/.codex/dotfiles.toml", 'model = "m"\n[features]\nhooks = true\n')
        self.write(self.dotfiles / "hermes/.hermes/config.yaml", "model: a\n")
        (self.home / ".mcporter").mkdir(parents=True)
        (self.home / ".mcporter/mcporter.json").symlink_to(self.manifest)
        self.write(self.home / ".codex/config.toml", 'model = "m"\n[features]\nhooks = true\n[projects."/x"]\ntrust_level = "trusted"\n')

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def check(self):
        return doctor.check(self.home, self.dotfiles)

    def test_matching_setup_passes(self):
        self.assertEqual(self.check(), ([], []))

    def test_dangling_skill_link_fails(self):
        (self.home / ".claude/skills").mkdir(parents=True)
        (self.home / ".claude/skills/gone").symlink_to(self.home / "missing")
        failures, _ = self.check()
        self.assertTrue(any("dangling link" in line and "gone" in line for line in failures))

    def test_secret_in_manifest_fails_but_a_variable_passes(self):
        servers = {"grafana": {"command": "uvx", "env": {"GRAFANA_SERVICE_ACCOUNT_TOKEN": "glsa_abc"}},
                   "posthog": {"url": "https://x", "headers": {"Authorization": "${POSTHOG_AUTH}"}}}
        self.manifest.write_text(json.dumps({"mcpServers": servers}))
        failures, _ = self.check()
        self.assertEqual(len(failures), 1)
        self.assertIn("GRAFANA_SERVICE_ACCOUNT_TOKEN", failures[0])

    def test_manifest_not_linked_fails(self):
        (self.home / ".mcporter/mcporter.json").unlink()
        self.write(self.home / ".mcporter/mcporter.json", self.manifest.read_text())
        failures, _ = self.check()
        self.assertTrue(any("is not a link" in line for line in failures))

    def test_server_defined_twice_fails(self):
        with open(self.home / ".codex/config.toml", "a") as config:
            config.write('[mcp_servers.grafana]\ncommand = "x"\n')
        self.write(self.home / ".claude.json", json.dumps({"mcpServers": {"grafana": {}}}))
        failures, _ = self.check()
        self.assertTrue(any("codex mcp remove grafana" in line for line in failures))
        self.assertTrue(any("claude mcp remove grafana" in line for line in failures))

    def test_codex_drift_fails(self):
        self.write(self.home / ".codex/config.toml", 'model = "other"\n[features]\nhooks = false\n')
        failures, _ = self.check()
        self.assertEqual(sorted(failures), ["codex features.hooks is False, dotfiles.toml says True", "codex model is 'other', dotfiles.toml says 'm'"])

    def test_hermes_drift_only_warns(self):
        self.write(self.home / ".hermes/config.yaml", "model: b\n")
        failures, warnings = self.check()
        self.assertEqual(failures, [])
        self.assertEqual(len(warnings), 1)


class YukeDoctorTests(AgentDoctorTests):
    def setUp(self):
        super().setUp()
        self.source = self.dotfiles / "yuke-rust/.config/yuke-rust"
        self.profile = self.home / ".config/yuke-rust"
        self.write(self.source / "config.json", json.dumps({"plugins": [{"path": "./plugins/models", "options": {"startupModel": "m", "tokenSpeed": True}}]}))
        self.write(self.source / "providers.json", json.dumps({"providers": [{"id": "bridge", "base_url": "http://127.0.0.1:1/v1", "api_key_env": "BRIDGE_KEY"}]}))
        self.write(self.source / "plugins/models/index.ts", "export {};\n")
        self.write(self.source / "plugins/models/__pycache__/x.pyc", "")
        for path in ("config.json", "providers.json", "plugins/models/index.ts"):
            (self.profile / path).parent.mkdir(parents=True, exist_ok=True)
            (self.profile / path).symlink_to(self.source / path)
        self.write(self.profile / "monid.key", "live-secret")
        self.write(self.profile / "tsconfig.json", "{}")

    def test_matching_setup_passes(self):
        self.assertEqual(self.check(), ([], []))

    def test_without_an_installed_profile_yuke_is_skipped(self):
        import shutil
        shutil.rmtree(self.profile)
        self.assertEqual(self.check(), ([], []))

    def test_profile_file_copied_instead_of_linked_fails(self):
        (self.profile / "config.json").unlink()
        self.write(self.profile / "config.json", (self.source / "config.json").read_text())
        failures, _ = self.check()
        self.assertEqual(len(failures), 1)
        self.assertIn("1 profile files are not links", failures[0])
        self.assertIn("config.json", failures[0])

    def test_profile_file_missing_fails(self):
        (self.profile / "plugins/models/index.ts").unlink()
        failures, _ = self.check()
        self.assertTrue(any("not links to dotfiles" in line for line in failures))

    def test_dangling_link_in_profile_fails(self):
        (self.profile / "plugins/old").mkdir(parents=True)
        (self.profile / "plugins/old/index.ts").symlink_to(self.source / "plugins/old/index.ts")
        failures, _ = self.check()
        self.assertEqual(len(failures), 1)
        self.assertIn("dangling link", failures[0])
        self.assertIn("plugins/old/index.ts", failures[0])

    def test_literal_credential_in_tracked_json_fails(self):
        (self.source / "providers.json").write_text(json.dumps({"providers": [{"id": "x", "api_key": "sk-live"}]}))
        failures, _ = self.check()
        self.assertEqual(len(failures), 1)
        self.assertIn("literal api_key", failures[0])

    def test_auth_file_in_package_fails(self):
        self.write(self.dotfiles / "yuke-rust/state/auth.json", "{}")
        failures, _ = self.check()
        self.assertEqual(len(failures), 1)
        self.assertIn("credential file", failures[0])


if __name__ == "__main__":
    unittest.main()
