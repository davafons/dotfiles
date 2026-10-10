import importlib.util
import os
from pathlib import Path
import unittest
import tomllib
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("sidebar_focus", Path(__file__).with_name("focus.py"))
focus = importlib.util.module_from_spec(spec)
spec.loader.exec_module(focus)


class FocusTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = {
            "focused_workspace_id": "w-other",
            "agents": [{"pane_id": f"w-agent:p{i}"} for i in range(1, 21)],
            "workspaces": [{"workspace_id": f"w{i}"} for i in range(1, 21)],
            "tabs": [{"tab_id": f"w-other:t{i}", "workspace_id": "w-other"} for i in range(1, 21)]
                    + [{"tab_id": f"w-caller:t{i}", "workspace_id": "w-caller"} for i in range(1, 21)],
        }
        self.api = patch.object(focus, "request", return_value={"snapshot": self.snapshot}).start()
        self.addCleanup(patch.stopall)

    def test_zero_binding_targets_tenth_agent_not_first_or_last(self):
        focus.focus("agent", 10)
        self.assertEqual(self.api.call_args.args, ("pane.focus", {"pane_id": "w-agent:p10"}))

    def test_second_bank_targets_every_position_from_eleven_to_twenty(self):
        with patch.dict(os.environ, {"HERDR_WORKSPACE_ID": "w-caller"}):
            for kind, target, id_prefix in (("agent", "pane", "w-agent:p"),
                                             ("workspace", "workspace", "w"),
                                             ("tab", "tab", "w-caller:t")):
                for number in range(11, 21):
                    with self.subTest(kind=kind, number=number):
                        focus.focus(kind, number)
                        self.assertEqual(self.api.call_args.args,
                                         (target + ".focus", {target + "_id": f"{id_prefix}{number}"}))

    def test_second_bank_config_and_manifest_agree(self):
        root = Path(__file__).resolve().parent
        config = tomllib.loads((root.parent.parent / "config.toml").read_text())
        manifest = tomllib.loads((root / "herdr-plugin.toml").read_text())
        actions = {action["id"]: action for action in manifest["actions"]}
        commands = {}
        for command in config["keys"]["command"]:
            keys = command["key"] if isinstance(command["key"], list) else [command["key"]]
            for key in keys:
                self.assertNotIn(key, commands, "Duplicate shortcut")
                commands[key] = command
        for kind, modifiers, context in (("tab", "", "pane"),
                                          ("agent", "ctrl+shift+", "global"),
                                          ("workspace", "shift+", "global")):
            for number in range(11, 21):
                with self.subTest(kind=kind, number=number):
                    command = commands[f"prefix+{modifiers}f{number - 10}"]
                    self.assertEqual(command["type"], "plugin_action")
                    self.assertEqual(command["command"], f"sidebar-numbers.{kind}-{number}")
                    action = actions[f"{kind}-{number}"]
                    self.assertEqual(action["contexts"], [context])
                    self.assertEqual(action["command"], ["python3", "focus.py", kind, str(number)])

    def test_scrollback_uses_control_e_and_no_bindings_require_alt(self):
        config = tomllib.loads((Path(__file__).resolve().parent.parent.parent / "config.toml").read_text())
        self.assertEqual(config["keys"]["edit_scrollback"], "prefix+ctrl+e")
        for field, binding in config["keys"].items():
            if field == "command":
                bindings = [key for command in binding for key in
                            (command["key"] if isinstance(command["key"], list) else [command["key"]])]
            else:
                bindings = binding if isinstance(binding, list) else [binding]
            for key in bindings:
                self.assertNotIn("alt", key.lower(), key)
                self.assertNotIn("option", key.lower(), key)

    def test_missing_second_bank_positions_do_not_focus_anything(self):
        self.snapshot["agents"] = self.snapshot["agents"][:15]
        self.snapshot["workspaces"] = self.snapshot["workspaces"][:15]
        self.snapshot["tabs"] = [tab for tab in self.snapshot["tabs"] if tab["tab_id"] != "w-caller:t20"]
        with patch.dict(os.environ, {"HERDR_WORKSPACE_ID": "w-caller"}):
            for kind in ("agent", "workspace", "tab"):
                with self.subTest(kind=kind):
                    self.api.reset_mock()
                    with self.assertRaisesRegex(RuntimeError, f"No {kind} at position 20"):
                        focus.focus(kind, 20)
                    self.assertEqual(self.api.call_count, 1)

    def test_tenth_workspace(self):
        focus.focus("workspace", 10)
        self.assertEqual(self.api.call_args.args, ("workspace.focus", {"workspace_id": "w10"}))

    def test_tab_uses_calling_workspace_not_other_client_focus(self):
        with patch.dict(os.environ, {"HERDR_WORKSPACE_ID": "w-caller"}):
            focus.focus("tab", 10)
        self.assertEqual(self.api.call_args.args, ("tab.focus", {"tab_id": "w-caller:t10"}))

    def test_missing_position_does_not_focus_anything(self):
        for number in (-1, 0, 21):
            self.api.reset_mock()
            with self.assertRaisesRegex(RuntimeError, "No agent at position"):
                focus.focus("agent", number)
            self.assertEqual(self.api.call_count, 1)

    def test_uses_current_order_after_reordering(self):
        self.snapshot["agents"].reverse()
        focus.focus("agent", 10)
        self.assertEqual(self.api.call_args.args, ("pane.focus", {"pane_id": "w-agent:p11"}))


if __name__ == "__main__":
    unittest.main(verbosity=2)
