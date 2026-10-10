#!/usr/bin/env python3
"""Real Herdr/Neovim round trip in a private session and detached tmux terminal."""

import hashlib
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

SESSION = "agent-tests-review-" + uuid.uuid4().hex[:8]
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
for key in list(ENV):
    if key.startswith("HERDR_"):
        ENV.pop(key)
HERDR = shutil.which("herdr")
TMUX = shutil.which("tmux")
NVIM = shutil.which("nvim")
server = None
address = None
evidence = {}


def run(argv, check=True, cwd=None):
    return subprocess.run(argv, env=ENV, cwd=cwd, check=check, capture_output=True, text=True, timeout=15)


def herdr(*args, check=True):
    return run([HERDR, "--session", SESSION, *args], check)


def api(method, params=None):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(10)
        connection.connect(str(address))
        connection.sendall((json.dumps({"id": "review-test", "method": method, "params": params or {}}) + "\n").encode())
        with connection.makefile("rb") as replies:
            reply = json.loads(replies.readline())
    assert "error" not in reply, reply
    return reply["result"]


def wait(condition, label, seconds=15):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        value = condition()
        if value:
            return value
        time.sleep(.1)
    raise AssertionError("Timed out: " + label)


def snapshot():
    return api("session.snapshot")["snapshot"]


def invoke(source):
    api("plugin.action.invoke", {"plugin_id": "david.review", "action_id": "toggle",
        "context": {"focused_pane_id": source["pane_id"], "workspace_id": source["workspace_id"],
                    "tab_id": source["tab_id"]}})


def review_record(source):
    key = hashlib.sha256((str(address) + source["pane_id"] + str(root)).encode()).hexdigest()[:16]
    nvim_socket = "/tmp/herdr-review-" + str(os.getuid()) + "/" + key + ".sock"
    def ready():
        response = run([NVIM, "--server", nvim_socket, "--remote-expr",
                        "luaeval('vim.env.HERDR_REVIEW_CONTEXT_PATH')"], check=False)
        if response.returncode or not response.stdout.strip():
            return None
        path = Path(response.stdout.strip())
        return json.loads(path.read_text()) if path.exists() else None
    return wait(ready, "review editor socket")


def lua(record, code):
    body = code if ";" in code else "return " + code
    expression = "luaeval(" + json.dumps("(function() " + body + " end)()") + ")"
    response = run([NVIM, "--server", record["nvim_socket"], "--remote-expr", expression])
    return response.stdout.strip()


temporary = tempfile.TemporaryDirectory(prefix="herdr-review-test-")
try:
    directory = temporary.name
    base = Path(directory)
    root = (base / "project with spaces").resolve()
    root.mkdir()
    (root / "sample.txt").write_text("context\nbefore\n")
    assert not (root / ".jj").exists()
    run(["jj", "git", "init", str(root)])
    run(["jj", "describe", "-m", "Review fixture baseline"], cwd=root)
    run(["jj", "new"], cwd=root)
    (root / "sample.txt").write_text("context\nafter\n")
    # Separate editor state avoids changing the user's sessions or recent files.
    ENV["XDG_STATE_HOME"] = str(base / "state")
    ENV["XDG_CACHE_HOME"] = str(base / "cache")
    with (base / "server.log").open("w") as log:
        server = subprocess.Popen([HERDR, "--session", SESSION, "server"], env=ENV, stdout=log, stderr=log)
        status = wait(lambda: (r.stdout if "status: running" in (r := herdr("status", check=False)).stdout else None), "server")
        address = Path(re.search(r"socket:\s*(.+)", status).group(1).strip())
        created = api("workspace.create", {"cwd": str(root), "label": "Agent Tests review", "focus": False})
        source = created["root_pane"]
        api("pane.report_agent", {"pane_id": source["pane_id"], "source": "test:review", "agent": "codex",
            "state": "idle", "agent_session_id": "00000000-0000-4000-a000-000000000001", "seq": 1})
        api("pane.report_agent_session", {"pane_id": source["pane_id"], "source": "herdr:codex", "agent": "codex",
            "agent_session_id": "00000000-0000-4000-a000-000000000001", "seq": 1})
        run([TMUX, "-L", SESSION, "new-session", "-d", "-s", "test", "-x", "180", "-y", "52",
             "exec " + shlex.quote(HERDR) + " --session " + shlex.quote(SESSION)])
        api("pane.focus", {"pane_id": source["pane_id"]})
        wait(lambda: run([TMUX,"-L",SESSION,"capture-pane","-t","test","-p"]).stdout.strip(), "test client")
        invoke(source)
        record = review_record(source)
        wait(lambda: lua(record, "vim.fn.exists(':HerdrReviewReturn')") == "2", "review setup")
        wait(lambda: "CodeDiff" in herdr("pane", "read", record["review_pane"], "--source", "visible").stdout
             or lua(record, "#vim.api.nvim_list_tabpages()") == "2", "real CodeDiff view")
        assert lua(record, "require('herdr-nvim.ask').target().pane_id") == source["pane_id"]
        assert lua(record, "require('codediff.config').options.diff.layout")  # Library configured.
        def rendered_diff():
            text=herdr("pane", "read", record["review_pane"], "--source", "visible").stdout
            return text if 'before' in text and 'after' in text else None
        evidence["initial_render"] = wait(rendered_diff,"before/after rendered in inline review")
        evidence["real_diff_opened"] = True
        assert lua(record, "require('codediff.ui.lifecycle').get_layout(vim.api.nvim_get_current_tabpage())") == "inline"
        assert lua(record, "require('codediff.ui.lifecycle').get_panel_view(vim.api.nvim_get_current_tabpage()).is_hidden") == "true"
        evidence["legacy_plugin_action_uses_inline_default_with_hidden_list"] = True
        evidence["agent_target"] = source["pane_id"]
        count = len(snapshot()["panes"])
        invoke(record | {"pane_id": record["review_pane"], "workspace_id": source["workspace_id"], "tab_id": source["tab_id"]})
        wait(lambda: snapshot()["focused_pane_id"] == source["pane_id"], "toggle return")
        invoke(source)
        wait(lambda: snapshot()["focused_pane_id"] == record["review_pane"], "reuse review")
        assert len(snapshot()["panes"]) == count, "Review duplicated its pane"
        evidence["reuse_and_toggle_return"] = True
        # Queue a real extmark annotation; preserve it and a modified file on return.
        lua(record, "vim.cmd('tabfirst'); vim.cmd('edit sample.txt'); vim.api.nvim_buf_set_lines(0,0,-1,false,{'unsaved'}); require('herdr-nvim.annotations').add(0,0,0,'Explain this change'); return true")
        lua(record, "vim.api.nvim_feedkeys(',ab','xt',false); return true")
        wait(lambda: snapshot()["focused_pane_id"] == source["pane_id"], "explicit return")
        invoke(source)
        wait(lambda: snapshot()["focused_pane_id"] == record["review_pane"], "reuse with edits")
        assert lua(record, "require('herdr-nvim.annotations').total()") == "1"
        assert lua(record, "vim.bo[vim.fn.bufnr('sample.txt')].modified") == "true"
        assert (root / "sample.txt").read_text() == "context\nafter\n"
        evidence["comments_and_unsaved_edits_preserved"] = True
        # No real agent submission: replace only the companion binary resolver
        # with a capture executable, while using the real sender and Herdr preflight.
        capture = base / "capture-send.py"
        capture_output = base / "send.json"
        capture.write_text("#!/usr/bin/env python3\nimport json,sys\nfrom pathlib import Path\nPath(" + repr(str(capture_output)) + ").write_text(json.dumps({'args':sys.argv[1:],'payload':json.load(sys.stdin)}))\nprint(json.dumps({'ok':True,'target':{'pane_id':" + repr(source["pane_id"]) + ",'agent':'codex'},'count':1}))\n")
        capture.chmod(0o700)
        lua(record, "require('herdr-nvim').config.binary=" + json.dumps(str(capture)) + "; require('herdr-nvim').send(); return true")
        wait(capture_output.exists, "annotation payload capture")
        submitted = json.loads(capture_output.read_text())
        assert submitted["args"][-2:] == ["--target", source["pane_id"]], submitted
        assert submitted["payload"]["comments"][0]["modified"] is True
        evidence["annotation_target_and_payload_verified_without_submission"] = True
        # Close only the diff tab: source focus returns and the editor survives.
        lua(record, "vim.cmd('tablast'); vim.api.nvim_feedkeys('q','xt',false); return true")
        wait(lambda: snapshot()["focused_pane_id"] == source["pane_id"], "q return")
        assert lua(record, "vim.bo[vim.fn.bufnr('sample.txt')].modified") == "true"
        invoke(source)
        wait(lambda: lua(record, "#vim.api.nvim_list_tabpages()") == "2", "reopen closed diff")
        evidence["q_returns_and_reopens_diff"] = True
        # A second source in the same checkout must have its own editor/target.
        other = api("pane.split", {"target_pane_id": source["pane_id"], "direction": "down", "cwd": str(root), "focus": False})["pane"]
        invoke(other)
        second = review_record(other)
        assert second["review_pane"] != record["review_pane"], "Sources shared one review editor"
        assert second["source_pane"] == other["pane_id"]
        evidence["distinct_source_editors"] = True
    # Simulate only the reported session metadata. Herdr's fake shell fixture
    # cannot change native Codex session identity without a real agent lifecycle.
    # The real upstream queue, preflight adapter and capture binary still run.
    assert record["source_session"], "Fixture session was not registered"
    replacement = dict(record["source_session"], value="00000000-0000-4000-a000-000000000002")
    fake_pane = api("pane.get", {"pane_id": source["pane_id"]})["pane"]
    fake_pane["agent_session"] = replacement
    lua(record, "_G.review_test_messages={}; vim.notify=function(message) table.insert(_G.review_test_messages,message) end; local original=vim.system; local response=" + json.dumps(json.dumps({"result":{"pane":fake_pane}})) + "; vim.system=function(args,opts,callback) if args[1]=='herdr' and args[2]=='pane' and args[3]=='get' then vim.schedule(function() callback({code=0,stdout=response,stderr=''}) end); return {} end; return original(args,opts,callback) end; return true")
    evidence["reported_session_change_test"] = "simulated metadata; real queue and sender adapter"
    capture_output.unlink()
    lua(record, "vim.cmd('tabfirst'); vim.api.nvim_set_current_buf(vim.fn.bufnr('sample.txt')); require('herdr-nvim.annotations').add(0,0,0,'New comment'); require('herdr-nvim').send(); return true")
    wait(lambda: lua(record, "require('herdr-nvim')._inflight") == "false", "stale-session rejection")
    assert not capture_output.exists(), "Comments sent to a replacement agent session"
    assert lua(record, "require('herdr-nvim.annotations').total()") == "1"
    evidence["reported_session_change_rejected_comments_kept"] = True
    # Explicit target selection accepts the new session; still only capture input.
    lua(record, "require('herdr-nvim').config.binary=nil; _G.review_previous_target=require('herdr-nvim.ask').target(); vim.ui.select=function(items,opts,callback) for _,item in ipairs(items) do if item.pane_id==" + json.dumps(source["pane_id"]) + " then callback(item); return end end end; require('config.herdr_review').choose_target(); return true")
    wait(lambda: lua(record, "require('herdr-nvim.ask').target() ~= _G.review_previous_target") == "true", "selected review target")
    lua(record, "require('herdr-nvim').config.binary=" + json.dumps(str(capture)) + "; require('herdr-nvim').send(); return true")
    wait(capture_output.exists, "explicit retarget capture")
    evidence["explicit_retarget_accepts_changed_session_metadata"] = True
    evidence["ok"] = True
finally:
    if address:
        evidence["plugin_logs"] = json.loads(herdr("plugin", "log", "list", "--plugin", "david.review", "--limit", "5", check=False).stdout)
        try:
            for item in snapshot()["panes"]:
                if item.get("agent") is None:
                    evidence.setdefault("rendered_views", []).append(herdr("pane", "read", item["pane_id"], "--source", "visible", check=False).stdout)
        except Exception:
            pass
    run([TMUX, "-L", SESSION, "kill-server"], check=False)
    if address:
        # Only the private test session and its periodic refresh job are stopped.
        herdr("plugin", "action", "invoke", "uninstall-refresh", "--plugin", "david.workspaces", check=False)
        herdr("session", "stop", SESSION, check=False)
        herdr("session", "delete", SESSION, check=False)
    if server:
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill();server.wait()
    temporary.cleanup()
    artifact = Path(os.environ.get('HERDR_REVIEW_TEST_ARTIFACT', str(Path(tempfile.gettempdir()) / 'herdr-review-integration-result.json')))
    artifact.write_text(json.dumps(evidence, indent=2) + '\n')
    print(json.dumps({k:v for k,v in evidence.items() if k not in ["plugin_logs", "rendered_views", "initial_render"]}, indent=2))
