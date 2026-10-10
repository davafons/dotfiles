import importlib.util
import os
from pathlib import Path
import unittest
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
