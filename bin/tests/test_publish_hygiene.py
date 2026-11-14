"""Check profile packages, credential exclusions, and Stow publication boundaries."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class PublishHygiene(unittest.TestCase):
    def test_profile_packages_exist_without_obsidian(self):
        for profile in sorted((ROOT / "profiles").glob("*.mk")):
            line = next(line for line in profile.read_text().splitlines()
                        if line.startswith("PROFILE_PACKAGES :="))
            packages = line.split(":=", 1)[1].split()
            self.assertNotIn("obsidian", packages, profile.name)
            for package in packages:
                self.assertTrue((ROOT / package).is_dir(), f"{profile.name}: {package}")
        self.assertFalse((ROOT / "obsidian").exists())
        self.assertNotIn('cask "obsidian"', (ROOT / "packages/Brewfile").read_text())

    @unittest.skipUnless(shutil.which("git"), "Git is required for ignore checks")
    def test_credentials_and_generated_files_are_ignored(self):
        ignored = [
            "yuke-rust/.config/yuke-rust/monid.key",
            "yuke-rust/.config/yuke-rust/tsconfig.json",
            "yuke-rust/.config/yuke-rust/.env",
            "yuke-rust/.config/yuke-rust/.env.local",
            "gh/.config/gh/hosts.yml",
            "ssh/.ssh/id_ed25519",
            "git-work/.gitconfig.local",
            "hermes/config.local.yaml",
            "bin/tests/__pycache__/fixture.pyc",
            "fxwald1le1.tmp",
        ]
        visible = ["yuke-rust/.config/yuke-rust/.env.example", "yuke-rust/.config/yuke-rust/config.json",
                   "yuke-rust/.config/yuke-rust/providers.json"]
        with tempfile.TemporaryDirectory(prefix="dotfiles-ignore-tests-") as directory:
            checkout = Path(directory)
            self.assertFalse((checkout / ".jj").exists())
            subprocess.run(["git", "init", "-q", directory], check=True)
            shutil.copyfile(ROOT / ".gitignore", checkout / ".gitignore")
            result = subprocess.run(
                ["git", "-C", directory, "check-ignore", "--stdin"],
                input="\n".join(ignored + visible) + "\n", capture_output=True, text=True,
                check=True,
            )
            self.assertEqual(result.stdout.splitlines(), ignored)

    @unittest.skipUnless(shutil.which("stow"), "GNU Stow is required")
    def test_neovim_stow_installs_config_without_submodule(self):
        config = ROOT / "nvim/.config/nvim"
        self.assertFalse((config / ".git").exists())
        self.assertFalse((ROOT / ".gitmodules").exists())
        with tempfile.TemporaryDirectory(prefix="dotfiles-nvim-stow-tests-") as home:
            subprocess.run(
                ["stow", "--no-folding", "-d", str(ROOT), "-t", home, "nvim"],
                capture_output=True, text=True, check=True,
            )
            installed = Path(home) / ".config/nvim"
            for name in ("init.lua", "lazy-lock.json", "lua/config/markdown_preview.lua",
                         "lua/plugins/colorscheme.lua"):
                link = installed / name
                self.assertTrue(link.is_symlink(), name)
                self.assertEqual(link.resolve(), config / name)
                self.assertEqual(link.read_bytes(), (config / name).read_bytes())
            self.assertFalse((installed / ".git").exists())
            self.assertFalse((Path(home) / "nvim.log").exists())
            self.assertFalse((Path(home) / ".ruby-lsp").exists())

    @unittest.skipUnless(shutil.which("stow"), "GNU Stow is required")
    def test_yuke_stow_plan_links_only_the_profile(self):
        self.assertFalse((ROOT / "yuke").exists())
        with tempfile.TemporaryDirectory(prefix="dotfiles-stow-tests-") as home:
            result = subprocess.run(
                ["stow", "--no-folding", "-n", "-v", "-d", str(ROOT), "-t", home, "yuke-rust"],
                capture_output=True, text=True, check=True,
            )
            output = result.stdout + result.stderr
            self.assertIn("LINK: .config/yuke-rust/config.json =>", output)
            self.assertIn("LINK: .config/yuke-rust/providers.json =>", output)
            self.assertIn("LINK: .config/yuke-rust/plugins/vim/plugin.json =>", output)
            for private in ("tests/", "scripts/", "state/", "skills/", "docs/", "biome.json"):
                self.assertNotIn(f"LINK: {private}", output)
            self.assertNotIn("__pycache__", output)
            for document in (ROOT / "yuke-rust").glob("*.md"):
                self.assertNotIn(f"LINK: {document.name} =>", output)
            self.assertEqual(list(Path(home).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
