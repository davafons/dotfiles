#!/usr/bin/env python3
"""Verify Code-last hooks and workspace identity in a private stock Herdr session."""

import json
import os
from pathlib import Path
import re
import shlex
import shutil
import socket
import subprocess
import tempfile
import time
import uuid

PLUGIN = Path(__file__).resolve().parents[1]
HERDR = os.environ.get("HERDR_CODE_TEST_BIN") or shutil.which("herdr")
TMUX = shutil.which("tmux")
SESSION = "at-code-" + uuid.uuid4().hex[:8]
ENV = {key: value for key, value in os.environ.items() if not key.startswith("HERDR_")}
ENV["PYTHONDONTWRITEBYTECODE"] = "1"
server = None
address = None


def run(argv, check=True):
    result = subprocess.run(argv, env=ENV, capture_output=True, text=True, timeout=20)
    if check and result.returncode:
        raise RuntimeError(str(argv) + "\n" + result.stdout + result.stderr)
    return result


def api(method, params=None):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(10)
        connection.connect(str(address))
        connection.sendall((json.dumps({"id": "code-order", "method": method, "params": params or {}}) + "\n").encode())
        with connection.makefile("rb") as replies:
            reply = json.loads(replies.readline())
    assert "error" not in reply, reply
    return reply["result"]


def wait(condition, label):
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        result = condition()
        if result:
            return result
        time.sleep(.1)
    raise AssertionError("Timed out: " + label)


with tempfile.TemporaryDirectory(prefix="co-", dir="/tmp") as temporary:
    base = Path(temporary).resolve()
    root = base / "project"
    linked = base / "linked"
    root.mkdir()
    linked.mkdir()
    ENV.update(HOME=str(base / "home"), XDG_CONFIG_HOME=str(base / "config"),
               HERDR_CONFIG_PATH=str(base / "config.toml"), XDG_STATE_HOME=str(base / "state"),
               XDG_CACHE_HOME=str(base / "cache"), SHELL="/bin/sh")
    Path(ENV["HOME"]).mkdir()
    (base / "config.toml").write_text('onboarding = false\n[terminal]\ndefault_shell = "/bin/sh"\nshell_mode = "non_login"\n[update]\nversion_check = false\nmanifest_check = false\n')
    candidate = base / "plugin"
    shutil.copytree(PLUGIN, candidate, ignore=shutil.ignore_patterns("__pycache__"))
    (candidate / "register.py").write_text(
        "import json,os\nfrom pathlib import Path\n"
        "base=Path(" + repr(str(base)) + ")\n"
        "state=Path(os.environ['HERDR_PLUGIN_STATE_DIR'])\n"
        "for number,record in enumerate(json.loads((base/'records.json').read_text())):\n"
        " record['herdr_socket']=os.environ['HERDR_SOCKET_PATH']\n"
        " (state/('code-test-'+str(number)+'.json')).write_text(json.dumps(record))\n"
        "(base/'registered.json').write_text(json.dumps({'state':str(state)}))\n")
    with (candidate / "herdr-plugin.toml").open("a") as manifest:
        manifest.write('\n[[actions]]\nid = "test-register"\ntitle = "Register test panes"\ncontexts = ["global"]\ncommand = ["python3", "register.py"]\n')
    evidence = {"herdr_binary": HERDR, "version": run([HERDR, "--version"]).stdout.strip()}
    try:
        run([HERDR, "--session", SESSION, "plugin", "link", str(candidate), "--enabled"])
        with (base / "server.log").open("w") as log:
            server = subprocess.Popen([HERDR, "--session", SESSION, "server"], env=ENV, stdout=log, stderr=log)
        def status():
            reply = run([HERDR, "--session", SESSION, "status"], check=False)
            return reply.stdout if "status: running" in reply.stdout else None
        address = Path(re.search(r"socket:\s*(.+)", wait(status, "private server")).group(1).strip())
        run([TMUX, "-L", SESSION, "new-session", "-d", "-s", "test", "-x", "120", "-y", "40",
             "exec " + shlex.quote(HERDR) + " --session " + shlex.quote(SESSION)])
        normal = api("workspace.create", {"cwd": str(root), "focus": False})["root_pane"]
        workspace = normal["workspace_id"]
        editor = api("tab.create", {"workspace_id": workspace, "cwd": str(linked), "focus": False})["root_pane"]
        spoof = api("tab.create", {"workspace_id": workspace, "cwd": str(root), "label": "Code", "focus": False})["root_pane"]
        second = api("tab.create", {"workspace_id": workspace, "cwd": str(linked), "focus": False})["root_pane"]
        custom = api("workspace.create", {"cwd": str(root), "label": "custom name", "focus": False})["root_pane"]
        custom_editor = api("tab.create", {"workspace_id": custom["workspace_id"], "cwd": str(linked), "focus": False})["root_pane"]
        records = [{"workspace_id": pane["workspace_id"], "editor_pane": pane["pane_id"],
                    "editor_terminal": pane["terminal_id"], "view": "tab", "view_generation": 4,
                    "source_pane": normal["pane_id"], "target": {"pane_id": "unchanged"}}
                   for pane in (editor, second, custom_editor)]
        (base / "records.json").write_text(json.dumps(records))
        api("plugin.action.invoke", {"plugin_id": "david.code", "action_id": "test-register"})
        wait(lambda: (base / "registered.json").exists(), "test records")
        state = Path(json.loads((base / "registered.json").read_text())["state"])
        def tabs(workspace_id=workspace):
            return [tab["tab_id"] for tab in api("tab.list", {"workspace_id": workspace_id})["tabs"]]
        def snapshot():
            return api("session.snapshot")["snapshot"]
        def label(workspace_id=workspace):
            return api("workspace.get", {"workspace_id": workspace_id})["workspace"]["label"]
        api("pane.focus", {"pane_id": normal["pane_id"]})
        api("plugin.action.invoke", {"plugin_id": "david.code", "action_id": "pin"})
        expected = [normal["tab_id"], spoof["tab_id"], editor["tab_id"], second["tab_id"]]
        wait(lambda: tabs() == expected, "initial Code-last group")
        wait(lambda: tabs(custom["workspace_id"]) == [custom["tab_id"], custom_editor["tab_id"]], "other workspace group")
        assert label() == "project"
        assert label(custom["workspace_id"]) == "custom name"
        assert snapshot()["focused_pane_id"] == normal["pane_id"]
        assert all(api("tab.get", {"tab_id": pane["tab_id"]})["tab"]["label"] == "Code" for pane in (editor, second, custom_editor))
        assert not api("pane.get", {"pane_id": spoof["pane_id"]})["pane"].get("tokens", {}).get("pane_kind")
        evidence["initial_order_labels_custom_name_and_ownership"] = True
        new = api("tab.create", {"workspace_id": workspace, "cwd": str(root), "focus": False})["root_pane"]
        expected.insert(2, new["tab_id"])
        wait(lambda: tabs() == expected, "new ordinary tab precedes Code")
        assert snapshot()["focused_pane_id"] == normal["pane_id"]
        api("tab.move", {"tab_id": editor["tab_id"], "insert_index": 0})
        wait(lambda: tabs() == expected, "Code moved first restores last group")
        assert snapshot()["focused_pane_id"] == normal["pane_id"]
        api("tab.move", {"tab_id": new["tab_id"], "insert_index": len(expected)})
        wait(lambda: tabs() == expected, "ordinary tab moved last restores Code suffix")
        for pane in (second, editor, normal):
            api("tab.focus", {"tab_id": pane["tab_id"]})
            wait(lambda: snapshot()["focused_pane_id"] == pane["pane_id"], "selected pane")
            assert tabs() == expected
            assert label() == "project", "Selecting an editor changed the first regular project name"
        evidence["create_move_focus_hooks_preserve_identity_and_order"] = True
        api("tab.close", {"tab_id": new["tab_id"]})
        expected.remove(new["tab_id"])
        wait(lambda: tabs() == expected, "ordinary close preserves group")
        api("tab.close", {"tab_id": editor["tab_id"]})
        expected.remove(editor["tab_id"])
        wait(lambda: tabs() == expected, "closed editor ignored")
        api("plugin.action.invoke", {"plugin_id": "david.code", "action_id": "pin"})
        time.sleep(.5)
        assert tabs() == expected
        assert snapshot()["focused_pane_id"] == normal["pane_id"]
        for number, original in enumerate(records):
            saved = json.loads((state / ("code-test-" + str(number) + ".json")).read_text())
            assert saved == dict(original, herdr_socket=str(address)), saved
        logs = run([HERDR, "--session", SESSION, "plugin", "log", "list", "--plugin", "david.code", "--limit", "100"]).stdout
        evidence["close_repeat_pin_preserve_records_and_focus"] = True
        evidence["plugin_logs"] = logs
        evidence["ok"] = True
    finally:
        if address:
            try:
                evidence["final_snapshot"] = api("session.snapshot")["snapshot"]
                evidence["plugin_logs"] = run([HERDR, "--session", SESSION, "plugin", "log", "list", "--plugin", "david.code", "--limit", "100"], check=False).stdout
            except (OSError, ValueError, AssertionError) as error:
                evidence["diagnostic_error"] = str(error)
        run([TMUX, "-L", SESSION, "kill-server"], check=False)
        if address:
            run([HERDR, "--session", SESSION, "session", "stop", SESSION], check=False)
            run([HERDR, "--session", SESSION, "session", "delete", SESSION], check=False)
        if server:
            try:
                server.wait(timeout=8)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()
        evidence["server_stopped"] = server is None or server.poll() is not None
        evidence["server_log"] = (base / "server.log").read_text() if (base / "server.log").exists() else "not started"
        artifact = Path(os.environ.get("HERDR_CODE_TEST_ARTIFACT", "/tmp/herdr-code-order-result.json"))
        artifact.write_text(json.dumps(evidence, indent=2) + "\n")
        print(json.dumps({key: value for key, value in evidence.items() if not key.endswith(("log", "logs", "snapshot"))}, indent=2))
        print("Artifact: " + str(artifact))
