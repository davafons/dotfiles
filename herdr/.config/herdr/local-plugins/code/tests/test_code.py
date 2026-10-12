import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import tomllib
import unittest
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location("workspace_code", Path(__file__).resolve().parents[1] / "code.py")
code = importlib.util.module_from_spec(spec)
spec.loader.exec_module(code)


class CodeTests(unittest.TestCase):
    def test_pinning_groups_owned_tabs_preserves_other_order_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, HERDR_PLUGIN_STATE_DIR=temporary):
            tabs = [{"tab_id": tab, "workspace_id": workspace, "label": "Code"}
                    for tab, workspace in [("n1", "w1"), ("a", "w1"), ("n2", "w1"), ("b", "w1"),
                                           ("fake", "w1"), ("n3", "w2"), ("c", "w2")]]
            panes = [{"pane_id": "p" + tab["tab_id"], "tab_id": tab["tab_id"],
                      "workspace_id": tab["workspace_id"], "terminal_id": "t" + tab["tab_id"]} for tab in tabs]
            paths = []
            for tab, workspace, terminal, priority in [("a", "w1", "ta", 10), ("b", "w1", "tb", 20),
                                                       ("c", "w2", "tc", 30), ("fake", "w1", "foreign", 50),
                                                       ("gone", "w1", "gone", 60), ("n3", "w1", "tn3", 70)]:
                path = Path(temporary) / ("code-" + tab + ".json")
                code.write_record(path, {"editor_pane": "p" + tab, "editor_terminal": terminal,
                                         "workspace_id": workspace, "pin_priority": priority,
                                         "view_generation": 4, "target": {"pane_id": "agent"}})
                paths.append(path)
            focused = ["pn1"]
            moves = []

            def request(method, params=None):
                if method == "session.snapshot":
                    return {"snapshot": {"tabs": list(tabs), "panes": panes, "focused_pane_id": focused[0]}}
                if method == "tab.rename":
                    tab = next(item for item in tabs if item["tab_id"] == params["tab_id"])
                    tab["label"] = params["label"]
                    return {"type": "ok"}
                if method == "pane.report_metadata":
                    self.assertEqual(params["source"], "plugin:david.code")
                    self.assertEqual(params["tokens"], {"pane_kind": "editor"})
                    owned = next(item for item in panes if item["pane_id"] == params["pane_id"])
                    owned.setdefault("tokens", {}).update(params["tokens"])
                    return {"type": "ok"}
                self.assertEqual(method, "tab.move", "Pinning must not focus panes or send input")
                tab = next(item for item in tabs if item["tab_id"] == params["tab_id"])
                indices = [i for i, item in enumerate(tabs) if item["workspace_id"] == tab["workspace_id"]]
                group = [tabs[i] for i in indices]
                group.remove(tab)
                group.insert(params["insert_index"], tab)
                for i, item in zip(indices, group):
                    tabs[i] = item
                moves.append(dict(params))
                return {"tabs": group}

            with patch.object(code, "request", side_effect=request), \
                    patch.object(code, "records", side_effect=lambda: [(p, json.loads(p.read_text())) for p in paths]):
                code.pin_tabs()
                self.assertEqual([item["tab_id"] for item in tabs], ["b", "a", "n1", "n2", "fake", "c", "n3"])
                self.assertEqual(focused[0], "pn1")
                self.assertEqual([item["pane_id"] for item in panes if item.get("tokens", {}).get("pane_kind") == "editor"], ["pa", "pb", "pc"])
                self.assertTrue(all(item["label"] == "Code" for item in tabs if item["tab_id"] in {"a", "b", "c"}))
                count = len(moves)
                code.pin_tabs()
                self.assertEqual(len(moves), count, "Already-pinned tabs must not generate more move events")
                code.pin_tabs(preferred_pane="pa")
                self.assertEqual([item["tab_id"] for item in tabs[:2]], ["a", "b"])
                focused[0] = "pb"
                code.pin_tabs(prefer_focused=True)
                self.assertEqual([item["tab_id"] for item in tabs[:2]], ["b", "a"])
                self.assertEqual([item["tab_id"] for item in tabs[2:]], ["n1", "n2", "fake", "c", "n3"])
            for path in paths:
                record = json.loads(path.read_text())
                self.assertEqual(record["view_generation"], 4)
                self.assertEqual(record["target"], {"pane_id": "agent"})

    def test_new_editor_host_uses_canonical_foreground_checkout(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, HERDR_SOCKET_PATH="socket",
                                                                    HERDR_PLUGIN_STATE_DIR=temporary):
            root = Path(temporary).resolve() / "checkout with spaces"
            (root / ".jj").mkdir(parents=True)
            nested = root / "src"
            nested.mkdir()
            source = {"pane_id": "w1:p1", "workspace_id": "w1", "cwd": "/wrong/repository",
                      "foreground_cwd": str(nested)}
            opened = {"plugin_pane": {"pane": {"pane_id": "w1:p3", "terminal_id": "t3", "tab_id": "w1:t2"}}}
            with patch.object(code, "pane", return_value=None), patch.object(code, "ready", return_value=True), \
                    patch.object(code, "remote"), patch.object(code, "pin_tabs"), \
                    patch.object(code, "request", return_value=opened) as request:
                _, record = code.ensure(source)
            self.assertEqual(record["root"], str(root))
            opened_params = request.call_args_list[0].args[1]
            self.assertEqual(opened_params["cwd"], str(root))
            self.assertEqual(opened_params["workspace_id"], "w1")

    def test_overlay_uses_same_checkout_as_editor(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "code.json"
            root = str(Path(temporary).resolve() / "checkout")
            code.write_record(path, {"view": "tab", "view_generation": 1, "source_pane": "w1:p1",
                                     "root": root, "nvim_socket": "fixture.sock"})
            with patch.object(code, "remote", return_value="0"), patch.object(code, "request") as request:
                code.show_overlay(path)
            params = request.call_args.args[1]
            self.assertEqual(params["cwd"], root)
            self.assertEqual(params["entrypoint"], "overlay")
            self.assertEqual(params["env"]["HERDR_CODE_CONTEXT_PATH"], str(path))

    def test_pane_launchers_use_absolute_plugin_script_not_checkout_script(self):
        manifest = tomllib.loads((code.ROOT / "herdr-plugin.toml").read_text())
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            plugin = root / "plugin with spaces and 'quotes'"
            checkout = root / "checkout with spaces"
            plugin.mkdir()
            checkout.mkdir()
            (checkout / "code.py").write_text("raise SystemExit('Wrong checkout script')\n")
            (plugin / "code.py").write_text("import sys; print(sys.argv[1])\n")
            for entry in manifest["panes"]:
                with self.subTest(entrypoint=entry["id"]):
                    result = subprocess.run(entry["command"], cwd=checkout,
                        env=dict(os.environ, HERDR_PLUGIN_ROOT=str(plugin)), capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout.strip(), "host" if entry["id"] == "code" else "ui-overlay")

    def test_editor_identity_is_checkout_and_workspace_not_agent(self):
        self.assertEqual(code.record_key("socket", "w1", "/repo"), code.record_key("socket", "w1", Path("/repo")))
        self.assertNotEqual(code.record_key("socket", "w1", "/repo"), code.record_key("socket", "w2", "/repo"))
        self.assertNotEqual(code.record_key("socket", "w1", "/repo"), code.record_key("other", "w1", "/repo"))
        self.assertNotEqual(code.record_key("socket", "w1", "/repo"), code.record_key("socket", "w1", "/linked"))

    def test_jj_root_without_git_is_valid_for_code(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root / ".jj").mkdir()
            (root / "nested").mkdir()
            self.assertEqual(code.repository(str(root / "nested")), ("jj", root))

    def test_nested_repository_wins(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root / ".jj").mkdir()
            child = root / "child"
            (child / ".git").mkdir(parents=True)
            self.assertEqual(code.repository(str(child)), ("git", child))

    def test_yuke_session_token_is_captured(self):
        target = code.target_of({"pane_id": "w1:p1", "agent": "yuke", "terminal_id": "t1",
                               "tokens": {"yuke_session_id": "session-1", "shortcut_number": "4"}})
        self.assertEqual(target["yuke_session_id"], "session-1")
        self.assertEqual(target["number"], "4")
        self.assertIsNone(code.target_of({"pane_id": "w1:p2"}))

    def test_chosen_agent_identity_must_still_match(self):
        chosen = {"pane_id": "w1:p1", "agent": "yuke", "terminal_id": "t1",
                  "tokens": {"yuke_session_id": "original", "summary": "Original task"}}
        replacements = [dict(chosen, terminal_id="new"), dict(chosen, agent="codex"),
                        dict(chosen, agent_session={"value": "new"}),
                        dict(chosen, tokens={"yuke_session_id": "replacement"})]
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "code.json"
            record = {"target": {"pane_id": "previous"}, "view": "tab", "view_generation": 4}
            code.write_record(path, record)
            for replacement in replacements:
                with self.subTest(replacement=replacement), patch.object(code, "pane", return_value=replacement), \
                        self.assertRaisesRegex(RuntimeError, "selected agent or session changed"):
                    code.set_target(path, chosen["pane_id"], code.target_of(chosen))
                self.assertEqual(json.loads(path.read_text()), record)

    def test_closed_chosen_agent_keeps_previous_recipient(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "code.json"
            record = {"target": {"pane_id": "previous"}}
            code.write_record(path, record)
            with patch.object(code, "pane", return_value=None), self.assertRaisesRegex(RuntimeError, "gone"):
                code.set_target(path, "closed", {"pane_id": "closed"})
            self.assertEqual(json.loads(path.read_text()), record)

    def test_changed_task_label_does_not_replace_agent_identity(self):
        chosen = {"pane_id": "w1:p1", "agent": "yuke", "terminal_id": "t1",
                  "tokens": {"yuke_session_id": "original", "summary": "Original task"}}
        current = dict(chosen, tokens={"yuke_session_id": "original", "summary": "Updated task"})
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "code.json"
            code.write_record(path, {"view_generation": 4})
            with patch.object(code, "pane", return_value=current):
                record = code.set_target(path, chosen["pane_id"], code.target_of(chosen))
            self.assertEqual(record["target"]["summary"], "Updated task")
            self.assertEqual(record["view_generation"], 4)

    def test_reuse_changes_return_destination_not_recipient(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, HERDR_SOCKET_PATH="socket",
                                                                    HERDR_PLUGIN_STATE_DIR=temporary):
            root = Path(temporary).resolve()
            (root / ".jj").mkdir()
            source = {"pane_id": "w1:p2", "workspace_id": "w1", "cwd": str(root), "agent": "codex"}
            target = {"pane_id": "w1:p1", "agent": "yuke", "yuke_session_id": "s1"}
            path = root / ("code-" + code.record_key("socket", "w1", root) + ".json")
            code.write_record(path, {"editor_pane": "w1:p3", "editor_terminal": "t3", "target": target,
                                     "source_pane": "w1:p1", "nvim_socket": "socket", "view": "tab"})
            with patch.object(code, "pane", return_value={"terminal_id": "t3"}), \
                    patch.object(code, "ready", return_value=True), patch.object(code, "remote"), \
                    patch.object(code, "pin_tabs"), patch.object(code, "request") as request:
                _, record = code.ensure(source)
            self.assertEqual(record["target"], target)
            self.assertEqual(record["source_pane"], "w1:p2")
            request.assert_not_called()
            self.assertEqual(json.loads(path.read_text())["target"], target)

    def test_reused_foreign_pane_is_refused(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, HERDR_SOCKET_PATH="socket",
                                                                    HERDR_PLUGIN_STATE_DIR=temporary):
            root = Path(temporary).resolve()
            (root / ".jj").mkdir()
            path = root / ("code-" + code.record_key("socket", "w1", root) + ".json")
            code.write_record(path, {"editor_pane": "w1:p3", "editor_terminal": "original"})
            source = {"pane_id": "w1:p1", "workspace_id": "w1", "cwd": str(root)}
            with patch.object(code, "pane", return_value={"terminal_id": "foreign"}), \
                    patch.object(code, "request") as request, self.assertRaisesRegex(RuntimeError, "different owner"):
                code.ensure(source)
            request.assert_not_called()

    def test_reopening_checkout_does_not_reuse_old_view_generation(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, HERDR_SOCKET_PATH="socket",
                                                                    HERDR_PLUGIN_STATE_DIR=temporary):
            root = Path(temporary).resolve()
            (root / ".jj").mkdir()
            source = {"pane_id": "w1:p1", "workspace_id": "w1", "cwd": str(root)}
            path = root / ("code-" + code.record_key("socket", "w1", root) + ".json")
            code.write_record(path, {"editor_pane": "closed", "view": "overlay", "view_generation": 41})
            opened = {"plugin_pane": {"pane": {"pane_id": "w1:p3", "terminal_id": "t3", "tab_id": "w1:t2"}}}
            with patch.object(code, "pane", return_value=None), patch.object(code, "ready", return_value=True), \
                    patch.object(code, "remote"), patch.object(code, "pin_tabs"), \
                    patch.object(code, "request", return_value=opened):
                _, record = code.ensure(source)
            self.assertGreater(record.get("view_generation", 0), 41)

    def test_old_overlay_exit_does_not_hide_its_replacement(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "code.json"
            code.write_record(path, {"view": "overlay", "view_generation": 1, "nvim_socket": "fixture.sock"})
            client = Mock()

            def exit_after_replacement():
                code.update(path, view="overlay")
                return 0

            client.poll.side_effect = exit_after_replacement
            with patch.object(code.signal, "signal"), patch.object(code, "remote", return_value="0"), \
                    patch.object(code.subprocess, "Popen", return_value=client), \
                    patch.object(code, "stop_child"), patch.object(code.time, "sleep"), \
                    patch.dict(os.environ, HERDR_CODE_VIEW_GENERATION="1"):
                code.run_surface(path)
            self.assertEqual(json.loads(path.read_text())["view"], "overlay")

    def test_delayed_overlay_start_does_not_attach_to_newer_request(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "code.json"
            code.write_record(path, {"view": "overlay", "view_generation": 2})
            with patch.object(code.signal, "signal"), patch.object(code, "remote") as remote, \
                    patch.object(code.subprocess, "Popen") as launch, patch.object(code, "stop_child"), \
                    patch.dict(os.environ, HERDR_CODE_VIEW_GENERATION="1"):
                code.run_surface(path)
            launch.assert_not_called()
            remote.assert_not_called()
            self.assertEqual(json.loads(path.read_text())["view"], "overlay")

    def test_failed_overlay_open_does_not_hide_newer_code_request(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "code.json"
            code.write_record(path, {"view": "tab", "view_generation": 1})

            def interrupted(_record, _expression):
                code.update(path, view="tab")
                raise RuntimeError("Old overlay request failed")

            with patch.object(code, "remote", side_effect=interrupted), self.assertRaisesRegex(RuntimeError, "Old overlay"):
                code.show_overlay(path)
            self.assertEqual(json.loads(path.read_text())["view"], "tab")

    def test_delayed_focus_event_does_not_replace_newer_overlay(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "code.json"
            record = {"view": "hidden", "view_generation": 1, "editor_pane": "w1:p2"}
            code.write_record(path, record)

            def delayed_record():
                code.update(path, view="overlay")
                yield path, record

            with patch.object(code, "request", return_value={"snapshot": {"focused_pane_id": "w1:p2"}}), \
                    patch.object(code, "records", side_effect=delayed_record), patch.object(code, "pin_tabs"):
                code.sync()
            self.assertEqual(json.loads(path.read_text())["view"], "overlay")

    def test_missing_return_pane_preserves_view(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "code.json"
            code.write_record(path, {"source_pane": "closed", "view": "overlay"})
            with patch.object(code, "pane", return_value=None), self.assertRaisesRegex(RuntimeError, "closed"):
                code.return_to_source(path)
            self.assertEqual(json.loads(path.read_text())["view"], "overlay")


if __name__ == "__main__":
    unittest.main()
