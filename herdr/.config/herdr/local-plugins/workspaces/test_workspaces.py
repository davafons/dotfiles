#!/usr/bin/env python3
"""Isolated repository tests; never touches user checkout history or GUI focus."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import tomllib
import unittest
from unittest.mock import patch

import workspaces as ws


class Checkouts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="herdr-workspaces-tests-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        config = self.base / "jj.toml"
        config.write_text('[user]\nname="Tests"\nemail="tests@example.invalid"\n[signing]\nbehavior="drop"\n')
        environment = patch.dict(os.environ, {"JJ_CONFIG": str(config), "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1", "HERDR_ENV": "1"})
        environment.start()
        self.addCleanup(environment.stop)

    def make_jj(self, name="project"):
        root = self.base / name
        ws.run(["jj", "git", "init", "--colocate", str(root)])
        (root / "file.txt").write_text("base\n")
        ws.run(["jj", "describe", "-m", "Initial"], root)
        ws.run(["jj", "bookmark", "create", "main", "-r", "@"], root)
        ws.run(["jj", "new", "main"], root)
        return root

    def make_git(self, name="git-project", commit=True):
        root = self.base / name
        root.mkdir()
        self.git(root, "init", "-b", "main")
        if commit:
            (root / "file.txt").write_text("base\n")
            self.git(root, "add", "file.txt")
            self.git(root, "-c", "user.name=Tests", "-c", "user.email=tests@example.invalid", "-c", "commit.gpgsign=false", "commit", "-m", "Initial")
        return root

    def git(self, root, *args):
        # Every Git mutation is restricted to Git-only temporary repositories.
        self.assertFalse((root / ".jj").exists())
        return ws.run(["git", "--no-optional-locks", "-C", str(root), *args])

    def snapshot(self, cwd, pane_id="w1:p1", workspace_id="w1"):
        pane = {"pane_id": pane_id, "workspace_id": workspace_id, "tab_id": workspace_id + ":t1", "cwd": str(cwd)}
        workspace = {"workspace_id": workspace_id, "active_tab_id": pane["tab_id"], "label": "unrelated label"}
        return {"workspaces": [workspace], "panes": [pane], "layouts": [{"tab_id": pane["tab_id"], "focused_pane_id": pane_id}]}

    def test_jj_status_is_read_only_and_never_calls_git(self):
        root = self.make_jj()
        (root / "file.txt").write_text("unsnapshotted\n")
        before = ws.jj(root, "op", "log", "--no-graph", "-T", 'id ++ "\\n"')
        original = ws.run
        def guard(argv, cwd=None):
            self.assertNotEqual(argv[0], "git")
            return original(argv, cwd)
        with patch.object(ws, "run", side_effect=guard):
            tokens = ws.status(root)
        self.assertEqual(tokens["checkout"], "default")
        self.assertEqual(tokens["vcs_status"], "empty")
        self.assertEqual(ws.jj(root, "op", "log", "--no-graph", "-T", 'id ++ "\\n"'), before)
        ws.run(["jj", "describe", "-m", "Recorded change"], root)
        self.assertEqual(ws.status(root)["vcs_status"], "1 file")
        self.assertEqual(ws.status(root)["change_description"], "Recorded change")

    def test_create_on_main_and_open_named_jj_workspace(self):
        root = self.make_jj()
        path = self.base / "worktrees" / "auth-fix"
        def api(method, params=None):
            if method == "session.snapshot":
                return {"snapshot": {"workspaces": [], "panes": [], "layouts": []}}
            if method == "workspace.create":
                self.assertFalse(params["focus"])
                self.assertEqual(params["cwd"], str(path))
                self.assertEqual(params["label"], "project / auth-fix")
                return {"workspace": {"workspace_id": "w2"}}
            self.fail(method)
        with patch.object(ws, "request", side_effect=api):
            ws.create_jj(root, "auth-fix", path, focus=False)
        self.assertEqual(ws.status(path)["checkout"], "auth-fix")
        self.assertEqual(ws.default_destination(path, "next"), ws.default_destination(root, "next"))
        self.assertEqual(ws.jj(path, "log", "-r", "@-", "--no-graph", "-T", "commit_id"), ws.jj(root, "log", "-r", "main", "--no-graph", "-T", "commit_id"))
        self.assertIn({"name": "auth-fix", "path": str(path)}, ws.jj_checkouts(root))
        with self.assertRaisesRegex(RuntimeError, "already exists"):
            ws.create_jj(root, "auth-fix", self.base / "another")
        with self.assertRaisesRegex(RuntimeError, "Destination already exists"):
            ws.create_jj(root, "another", path)
        with self.assertRaisesRegex(RuntimeError, "Use a name"):
            ws.create_jj(root, "../bad", self.base / "bad")

    def test_missing_main_does_not_create_destination(self):
        root = self.make_jj()
        ws.run(["jj", "bookmark", "delete", "main"], root)
        target = self.base / "missing" / "checkout"
        with self.assertRaises(RuntimeError):
            ws.create_jj(root, "checkout", target)
        self.assertFalse(target.parent.exists())

    def test_created_checkout_survives_api_failure(self):
        root = self.make_jj()
        target = self.base / "retry"
        with patch.object(ws, "request", side_effect=RuntimeError("server unavailable")):
            with self.assertRaisesRegex(RuntimeError, "open-existing to retry"):
                ws.create_jj(root, "retry", target)
        self.assertTrue((target / ".jj").exists())

    def test_open_reuses_pane_in_inactive_tab(self):
        root = self.make_jj()
        snapshot = self.snapshot(self.base)
        snapshot["panes"].append({"pane_id": "w1:p2", "workspace_id": "w1", "tab_id": "w1:t2", "foreground_cwd": str(root)})
        with patch.object(ws, "request", side_effect=[{"snapshot": snapshot}, {}]) as api:
            result = ws.open_jj(root, "default")
        self.assertEqual(result["workspace_id"], "w1")
        self.assertEqual(api.call_args_list[-1].args, ("pane.focus", {"pane_id": "w1:p2"}))
        with patch.object(ws, "request", return_value={"snapshot": snapshot}) as api:
            ws.open_jj(root, "default", focus=False)
            self.assertEqual(api.call_count, 1)

    def test_saved_jj_conflict_status(self):
        root = self.make_jj()
        (root / "file.txt").write_text("left\n")
        ws.run(["jj", "describe", "-m", "Left"], root)
        ws.run(["jj", "bookmark", "create", "left"], root)
        ws.run(["jj", "new", "main"], root)
        (root / "file.txt").write_text("right\n")
        ws.run(["jj", "describe", "-m", "Right"], root)
        ws.run(["jj", "bookmark", "create", "right"], root)
        ws.run(["jj", "new", "left", "right"], root)
        self.assertIn("CONFLICT", ws.status(root)["vcs_status"])

    def test_git_worktree_names_dirty_rename_and_detached_head(self):
        root = self.make_git()
        path = self.base / "git-feature"
        self.git(root, "worktree", "add", "-b", "auth-fix", str(path))
        (path / "file.txt").write_text("modified\n")
        (path / "space name.txt").write_text("new\n")
        tokens = ws.status(path)
        self.assertEqual(tokens["checkout"], "git-feature")
        self.assertEqual(tokens["revision"], "auth-fix")
        self.assertEqual(tokens["vcs_status"], "2 files")
        self.git(path, "restore", "file.txt")
        (path / "space name.txt").unlink()
        self.git(path, "mv", "file.txt", "renamed file.txt")
        self.assertEqual(ws.status(path)["vcs_status"], "1 file")
        self.git(path, "reset", "--hard", "HEAD")
        self.git(path, "checkout", "--detach")
        self.assertTrue(ws.status(path)["revision"].startswith("detached "))
        self.assertEqual(ws.status(path)["vcs_status"], "clean")

    def test_git_unborn_branch(self):
        root = self.make_git(commit=False)
        self.assertEqual(ws.status(root)["revision"], "main")
        self.assertEqual(ws.status(root)["vcs_status"], "clean")

    def test_nested_repo_boundary_and_no_repo(self):
        root = self.make_jj()
        nested = root / "nested"
        nested.mkdir()
        self.git(nested, "init", "-b", "main")
        self.assertEqual(ws.repository(nested), ("git", nested))
        self.assertEqual(ws.repository(root), ("jj", root))
        self.assertEqual(ws.status(self.base), {key: None for key in ws.TOKENS})
        self.assertEqual(ws.status(self.base / "missing"), {key: None for key in ws.TOKENS})

    def test_workspace_active_tab_and_agent_independent_checkout(self):
        snapshot = self.snapshot(self.base)
        workspace = snapshot["workspaces"][0]
        snapshot["panes"].insert(0, {"pane_id": "w1:p2", "workspace_id": "w1", "tab_id": "w1:t2", "focused": True, "cwd": "/wrong"})
        self.assertEqual(ws.active_pane(snapshot, workspace)["pane_id"], "w1:p1")
        self.assertEqual(ws.pane_cwd({"cwd": "/initial", "foreground_cwd": "/active"}), "/active")

    def test_editor_panel_does_not_supply_workspace_checkout(self):
        snapshot = self.snapshot(self.base)
        workspace = snapshot["workspaces"][0]
        snapshot["panes"][0]["tokens"] = {"pane_kind": "editor"}
        snapshot["panes"].append({"pane_id": "w1:p2", "workspace_id": "w1", "tab_id": "w1:t2", "cwd": "/work/yuke"})
        self.assertEqual(ws.active_pane(snapshot, workspace)["pane_id"], "w1:p2")

    def test_sync_caches_repo_status_and_clears_non_repo(self):
        snapshot = self.snapshot(self.base)
        snapshot["panes"].append(dict(snapshot["panes"][0], pane_id="w1:p2"))
        def api(method, params=None):
            if method == "session.snapshot":
                return {"snapshot": snapshot}
            self.assertIn(method, {"workspace.report_metadata", "pane.report_metadata"})
            self.assertEqual(params["tokens"], {key: None for key in ws.TOKENS})
            self.assertEqual(params["source"], ws.SOURCE)
            return {}
        with patch.dict(os.environ, {"HERDR_PLUGIN_STATE_DIR": str(self.base / "state"), "HERDR_SOCKET_PATH": "/tmp/tests.sock"}), patch.object(ws, "request", side_effect=api) as api, patch.object(ws, "status", wraps=ws.status) as status:
            ws.sync()
        self.assertEqual(status.call_count, 1)
        self.assertEqual(api.call_count, 4)

    def test_picker_cancel_and_index_not_untrusted_path(self):
        with patch.object(ws.shutil, "which", return_value="fzf"), patch.object(ws.subprocess, "run", return_value=subprocess.CompletedProcess([], 130, "")):
            self.assertIsNone(ws.choose(["one", "two"], "Test"))
        with patch.object(ws.shutil, "which", return_value="fzf"), patch.object(ws.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "1\tuser label\n")):
            self.assertEqual(ws.choose(["one", "two"], "Test"), 1)

    def test_popup_action_uses_session_modal_api_without_targets(self):
        with patch.object(ws, "origin", return_value="/checkout"), patch.object(ws, "request") as api:
            ws.open_popup("create")
        method, params = api.call_args.args
        self.assertEqual(method, "plugin.pane.open")
        self.assertEqual(params["env"]["HERDR_CHECKOUT_ORIGIN"], "/checkout")
        self.assertNotIn("workspace_id", params)
        self.assertNotIn("target_pane_id", params)
        self.assertNotIn("cwd", params)

    def test_popup_ui_routes_git_and_jj(self):
        git_root = self.make_git()
        item = {"path": str(git_root), "branch": "main", "is_bare": False, "is_prunable": False}
        with patch.dict(os.environ, {"HERDR_CHECKOUT_ORIGIN": str(git_root)}), patch.object(ws, "choose", return_value=0), patch.object(ws, "request", side_effect=[{"worktrees": [item]}, {}]) as api, patch.object(ws, "sync"):
            ws.ui("open")
        self.assertEqual(api.call_args_list[-1].args[0], "worktree.open")
        root = self.make_jj()
        with patch.dict(os.environ, {"HERDR_CHECKOUT_ORIGIN": str(root)}), patch.object(ws, "choose", return_value=0), patch.object(ws, "open_jj") as opened, patch.object(ws, "sync"):
            ws.ui("open")
        opened.assert_called_once_with(str(root), "default")

    def test_startup_does_not_register_background_jobs(self):
        manifest = tomllib.loads(Path(ws.__file__).with_name("herdr-plugin.toml").read_text())
        bin_dir = self.base / "bin"
        bin_dir.mkdir()
        calls = self.base / "launchctl-calls"
        launchctl = bin_dir / "launchctl"
        launchctl.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$LAUNCHCTL_CALLS"\n')
        launchctl.chmod(0o755)
        environment = dict(os.environ, HOME=str(self.base),
                           HERDR_SOCKET_PATH=str(self.base / "missing.sock"),
                           HERDR_PLUGIN_STATE_DIR=str(self.base / "state"),
                           LAUNCHCTL_CALLS=str(calls), PATH=f"{bin_dir}:{os.environ['PATH']}")
        for hook in manifest.get("startup", []):
            if "macos" in hook.get("platforms", ["macos"]):
                result = subprocess.run(hook["command"], cwd=Path(ws.__file__).parent,
                                        env=environment, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.base / "Library" / "LaunchAgents").exists())
        self.assertFalse(calls.exists())
        for action in manifest["actions"]:
            self.assertNotIn("install-refresh", action["command"])

    def test_event_metadata_does_not_expire_without_a_timer(self):
        snapshot = self.snapshot(self.base)
        def api(method, params=None):
            if method == "session.snapshot":
                return {"snapshot": snapshot}
            self.assertIsNone(params.get("ttl_ms"))
            return {}
        with patch.dict(os.environ, {"HERDR_PLUGIN_STATE_DIR": str(self.base / "state"), "HERDR_SOCKET_PATH": "/tmp/tests.sock"}), patch.object(ws.sys, "platform", "darwin"), patch.object(ws, "request", side_effect=api):
            ws.sync()

    def test_refresh_respects_plugin_disable(self):
        for enabled in (True, False):
            with patch.object(ws, "request", return_value={"plugins": [{"plugin_id": ws.PLUGIN, "enabled": enabled}]}):
                self.assertEqual(ws.refresh_enabled(), enabled)
        with patch.object(ws, "request", return_value={"plugins": []}):
            self.assertFalse(ws.refresh_enabled())

    def test_uninstall_removes_only_the_current_session_legacy_timer(self):
        socket_path = "/tmp/tests.sock"
        digest = ws.hashlib.sha256(socket_path.encode()).hexdigest()[:12]
        label = f"dev.herdr.workspaces.{digest}"
        directory = self.base / "Library" / "LaunchAgents"
        directory.mkdir(parents=True)
        timer = directory / f"{label}.plist"
        timer.write_text("legacy timer")
        unrelated = directory / "com.example.other.plist"
        unrelated.write_text("leave alone")
        with patch.dict(os.environ, {"HERDR_SOCKET_PATH": socket_path}), patch.object(ws.Path, "home", return_value=self.base), patch.object(ws.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as launchctl:
            ws.uninstall_refresh()
            self.assertFalse(timer.exists())
            self.assertEqual(unrelated.read_text(), "leave alone")
            launchctl.assert_called_once_with(["launchctl", "bootout", f"gui/{os.getuid()}/{label}"], capture_output=True)
            ws.uninstall_refresh()

    def test_sidebar_strings_strip_controls(self):
        self.assertEqual(ws.clean("Login\n\tfix\x00"), "Login fix")
        self.assertEqual(len(ws.clean("x" * 1000)), 80)


if __name__ == "__main__":
    unittest.main(verbosity=2)
