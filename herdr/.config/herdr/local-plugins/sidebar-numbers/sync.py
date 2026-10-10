#!/usr/bin/env python3
"""Publish shortcut positions and mark tabs that contain detected agents."""

import fcntl
import json
import os
from pathlib import Path
import re
import socket


STATUS_ICONS = {
    "blocked": "●",
    "working": "●",
    "done": "●",
    "idle": "○",
    "unknown": "·",
}
# Restore names from grouped badges and both earlier label formats.
NUMBERS = r"(?:[1-9]\d*(?:,[1-9]\d*)*)"
SHORTCUTS = rf"\[{NUMBERS}\]"
ICON = r"(?:[●×◐✓○·]|🤖)"
TAB_MARKER = re.compile(rf"^(?:\[{NUMBERS}\s+{ICON}\]|{SHORTCUTS}\s+{ICON}|{ICON}{SHORTCUTS})\s+")


def load_tab_labels(path):
    """Load tab names managed by an earlier sync, ignoring stale state."""
    try:
        labels = json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    return labels if isinstance(labels, dict) else {}


def save_tab_labels(path, labels):
    """Atomically save managed tab names for the next event invocation."""
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(labels, sort_keys=True) + "\n")
    temporary.replace(path)


def base_tab_label(label):
    """Remove a plugin marker left behind after state loss or a failed sync."""
    return TAB_MARKER.sub("", label, count=1)


def sync():
    """Update changed shortcut tokens and agent markers from one snapshot."""
    state_dir = Path(os.environ["HERDR_PLUGIN_STATE_DIR"])
    state_dir.mkdir(parents=True, exist_ok=True)
    with (state_dir / "sync.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)

        def request(method, params):
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
                connection.settimeout(5)
                connection.connect(os.environ["HERDR_SOCKET_PATH"])
                with connection.makefile("rb") as replies:
                    message = {"id": "sidebar-numbers", "method": method, "params": params}
                    connection.sendall((json.dumps(message) + "\n").encode())
                    response = json.loads(replies.readline())
                    if "error" in response:
                        raise RuntimeError(response["error"])
                    return response["result"]

        snapshot = request("session.snapshot", {})["snapshot"]
        agent_numbers_by_tab = {}
        for kind, resources in (("workspace", snapshot["workspaces"]),
                                ("pane", snapshot["agents"])):
            for index, resource in enumerate(resources, 1):
                resource_id = resource[kind + "_id"]
                number = "0" if index == 10 else str(index)
                previous = resource.get("tokens", {}).get("shortcut_number")
                if previous != number:
                    request(kind + ".report_metadata", {
                        kind + "_id": resource_id,
                        "source": "plugin:sidebar-numbers",
                        "tokens": {"shortcut_number": number},
                    })
                if kind == "pane":
                    agent_numbers_by_tab.setdefault(resource["tab_id"], []).append(str(index))

        labels_path = state_dir / "tab-labels.json"
        managed_labels = load_tab_labels(labels_path)
        live_tab_ids = {tab["tab_id"] for tab in snapshot["tabs"]}
        managed_labels = {
            tab_id: details for tab_id, details in managed_labels.items()
            if tab_id in live_tab_ids and isinstance(details, dict)
        }

        for tab in snapshot["tabs"]:
            tab_id = tab["tab_id"]
            current = tab["label"]
            managed = managed_labels.get(tab_id)
            if managed and current == managed.get("rendered"):
                base = managed.get("base", base_tab_label(current))
            else:
                # A different current value is a manual rename. Preserve it while
                # dropping any orphaned marker from an interrupted earlier sync.
                base = base_tab_label(current)

            numbers = agent_numbers_by_tab.get(tab_id, [])
            if numbers:
                icon = STATUS_ICONS.get(tab.get("agent_status"), STATUS_ICONS["unknown"])
                rendered = f"[{','.join(numbers)} {icon}] {base}"
                if current != rendered:
                    request("tab.rename", {"tab_id": tab_id, "label": rendered})
                managed_labels[tab_id] = {"base": base, "rendered": rendered}
            else:
                rendered = base if managed or TAB_MARKER.match(current) else current
                if current != rendered:
                    request("tab.rename", {"tab_id": tab_id, "label": rendered})
                managed_labels.pop(tab_id, None)

        save_tab_labels(labels_path, managed_labels)


if __name__ == "__main__":
    sync()
