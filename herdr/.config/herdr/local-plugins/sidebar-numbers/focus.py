#!/usr/bin/env python3
"""Focus a sidebar position using the same snapshot order as its numbers."""

import argparse
import json
import os
import socket
import sys


def request(method, params=None):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(5)
        connection.connect(os.environ["HERDR_SOCKET_PATH"])
        connection.sendall((json.dumps({"id": "sidebar-numbers-focus", "method": method,
                                       "params": params or {}}) + "\n").encode())
        with connection.makefile("rb") as replies:
            response = json.loads(replies.readline())
    if "error" in response:
        raise RuntimeError(str(response["error"]))
    return response["result"]


def focus(kind, number):
    snapshot = request("session.snapshot")["snapshot"]
    if kind == "agent":
        resources, target = snapshot["agents"], "pane"
    elif kind == "workspace":
        resources, target = snapshot["workspaces"], "workspace"
    else:
        workspace = os.environ.get("HERDR_WORKSPACE_ID") or snapshot.get("focused_workspace_id")
        resources = [tab for tab in snapshot["tabs"] if tab["workspace_id"] == workspace]
        target = "tab"
    if number < 1 or number > len(resources):
        raise RuntimeError(f"No {kind} at position {number} ({len(resources)} available)")
    resource = resources[number - 1]
    request(target + ".focus", {target + "_id": resource[target + "_id"]})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=("agent", "workspace", "tab"))
    parser.add_argument("number", type=int)
    args = parser.parse_args()
    try:
        focus(args.kind, args.number)
    except (RuntimeError, OSError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
