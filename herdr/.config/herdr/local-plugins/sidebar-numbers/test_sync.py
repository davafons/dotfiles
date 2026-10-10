import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("sidebar_numbers", Path(__file__).with_name("sync.py"))
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


class FakeSocket:
    def __init__(self, dispatch):
        self.dispatch = dispatch

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def settimeout(self, _):
        pass

    def connect(self, _):
        pass

    def sendall(self, data):
        request = json.loads(data)
        self.response = {"id": request["id"], "result": self.dispatch(request["method"], request["params"])}

    def makefile(self, _):
        return self

    def readline(self):
        return (json.dumps(self.response) + "\n").encode()


class SidebarNumbersTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="sidebar-numbers-test-")
        self.addCleanup(self.directory.cleanup)
        self.state = Path(self.directory.name)
        self.snapshot = {
            "workspaces": [{"workspace_id": "w1", "tokens": {}}],
            "agents": [
                {"pane_id": "w1:p1", "tab_id": "w1:t1", "tokens": {}},
                {"pane_id": "w1:p2", "tab_id": "w1:t1", "tokens": {}},
            ],
            "tabs": [
                {"tab_id": "w1:t1", "label": "◐[8] review", "agent_status": "working"},
                {"tab_id": "w1:t2", "label": "○[9] shell", "agent_status": "unknown"},
            ],
        }
        self.calls = []

    def dispatch(self, method, params):
        self.calls.append((method, params))
        if method == "session.snapshot":
            return {"snapshot": copy.deepcopy(self.snapshot)}
        if method == "tab.rename":
            tab = next(tab for tab in self.snapshot["tabs"] if tab["tab_id"] == params["tab_id"])
            tab["label"] = params["label"]
        elif method in ("workspace.report_metadata", "pane.report_metadata"):
            kind = method.split(".")[0]
            resources = self.snapshot["workspaces" if kind == "workspace" else "agents"]
            resource = next(item for item in resources if item[kind + "_id"] == params[kind + "_id"])
            resource["tokens"].update(params["tokens"])
        else:
            raise AssertionError(method)
        return {}

    def refresh(self):
        with patch.dict(os.environ, {"HERDR_PLUGIN_STATE_DIR": str(self.state), "HERDR_SOCKET_PATH": "/test/socket"}), patch.object(sync.socket, "socket", side_effect=lambda *_: FakeSocket(self.dispatch)):
            sync.sync()

    def test_default_dots_and_legacy_prefix_cleanup(self):
        self.assertEqual(sync.STATUS_ICONS, {"blocked": "●", "working": "●", "done": "●", "idle": "○", "unknown": "·"})
        for marker in ("●", "×", "◐", "✓", "○", "·", "🤖"):
            self.assertEqual(sync.base_tab_label(f"{marker}[1,12] review"), "review")
            self.assertEqual(sync.base_tab_label(f"[1,12] {marker} review"), "review")
            self.assertEqual(sync.base_tab_label(f"[1,12 {marker}] review"), "review")
        for label in ("● ordinary name", "○[0] name", "●[] name", "●[1,] name"):
            self.assertEqual(sync.base_tab_label(label), label)

    def test_sync_preserves_base_names_and_all_agent_numbers(self):
        self.refresh()
        self.assertEqual(self.snapshot["tabs"][0]["label"], "[1,2 ●] review")
        self.assertEqual(self.snapshot["tabs"][1]["label"], "shell")
        self.assertEqual(sync.load_tab_labels(self.state / "tab-labels.json")["w1:t1"]["base"], "review")
        self.assertEqual([pane["tokens"]["shortcut_number"] for pane in self.snapshot["agents"]], ["1", "2"])

    def test_twenty_entries_show_zero_at_ten_and_keep_tab_badges_numeric(self):
        self.snapshot["workspaces"] = [{"workspace_id": f"w{i}", "tokens": {}} for i in range(1, 21)]
        self.snapshot["agents"] = [{"pane_id": f"w1:p{i}", "tab_id": "w1:t1", "tokens": {}} for i in range(1, 21)]
        self.refresh()
        expected = [str(i) if i != 10 else "0" for i in range(1, 21)]
        self.assertEqual([pane["tokens"]["shortcut_number"] for pane in self.snapshot["agents"]], expected)
        self.assertEqual([workspace["tokens"]["shortcut_number"] for workspace in self.snapshot["workspaces"]], expected)
        self.assertEqual(self.snapshot["tabs"][0]["label"], "[" + ",".join(str(i) for i in range(1, 21)) + " ●] review")
        self.calls.clear()
        self.refresh()
        self.assertEqual([method for method, _ in self.calls], ["session.snapshot"])

    def test_number_first_labels_survive_missing_managed_state(self):
        self.snapshot["tabs"][0]["label"] = "[8] ● review"
        self.refresh()
        self.assertEqual(self.snapshot["tabs"][0]["label"], "[1,2 ●] review")
        self.snapshot["agents"] = []
        self.refresh()
        self.assertEqual(self.snapshot["tabs"][0]["label"], "review")

    def test_grouped_badges_survive_missing_managed_state(self):
        self.snapshot["tabs"][0]["label"] = "[8 ●] review"
        self.refresh()
        self.assertEqual(self.snapshot["tabs"][0]["label"], "[1,2 ●] review")
        (self.state / "tab-labels.json").unlink()
        self.refresh()
        self.assertEqual(self.snapshot["tabs"][0]["label"], "[1,2 ●] review")

    def test_repeat_refresh_does_not_duplicate_markers_or_rename(self):
        self.refresh()
        self.calls.clear()
        self.refresh()
        self.assertEqual([method for method, _ in self.calls], ["session.snapshot"])

    def test_manual_rename_is_preserved_across_status_changes(self):
        self.refresh()
        self.snapshot["tabs"][0].update(label="my review", agent_status="idle")
        self.refresh()
        self.assertEqual(self.snapshot["tabs"][0]["label"], "[1,2 ○] my review")
        self.snapshot["tabs"][0]["agent_status"] = "blocked"
        self.refresh()
        self.assertEqual(self.snapshot["tabs"][0]["label"], "[1,2 ●] my review")

    def test_agent_exit_restores_original_tab_name(self):
        self.refresh()
        self.snapshot["agents"] = []
        self.refresh()
        self.assertEqual(self.snapshot["tabs"][0]["label"], "review")
        self.assertEqual(sync.load_tab_labels(self.state / "tab-labels.json"), {})


if __name__ == "__main__":
    unittest.main(verbosity=2)
