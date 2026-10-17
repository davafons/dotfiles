#!/usr/bin/env python3
"""Exercise Code tab, overlay and guarded routing in a private Herdr session."""

import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import socket
import subprocess
import tempfile
import time
import uuid

SESSION = "agent-tests-code-" + uuid.uuid4().hex[:8]
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
for key in list(ENV):
    if key.startswith("HERDR_"):
        ENV.pop(key)
HERDR = os.environ.get("HERDR_CODE_TEST_BIN") or shutil.which("herdr")
TMUX = shutil.which("tmux")
NVIM = shutil.which("nvim")
PLUGIN = Path(__file__).resolve().parents[1]
server = None
address = None
record = None
paths = []
evidence = {"herdr_binary": HERDR}


def run(argv, check=True, cwd=None):
    return subprocess.run(argv, env=ENV, cwd=cwd, check=check, capture_output=True, text=True, timeout=20)


def herdr(*args, check=True):
    return run([HERDR, "--session", SESSION, *args], check)


def api(method, params=None):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(10)
        connection.connect(str(address))
        connection.sendall((json.dumps({"id": "code-test", "method": method, "params": params or {}}) + "\n").encode())
        with connection.makefile("rb") as replies:
            reply = json.loads(replies.readline())
    assert "error" not in reply, reply
    return reply["result"]


def wait(condition, label, seconds=20):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        value = condition()
        if value:
            return value
        time.sleep(.1)
    raise AssertionError("Timed out: " + label)


def snapshot():
    return api("session.snapshot")["snapshot"]


def tab_ids(workspace):
    return [tab["tab_id"] for tab in api("tab.list", {"workspace_id": workspace})["tabs"]]


def invoke(source, action="toggle"):
    api("plugin.action.invoke", {"plugin_id": "david.code", "action_id": action,
        "context": {"focused_pane_id": source["pane_id"], "workspace_id": source["workspace_id"],
                    "tab_id": source["tab_id"]}})


def editor_record(source, root):
    key = hashlib.sha256(json.dumps([str(address), source["workspace_id"], str(root)]).encode()).hexdigest()[:20]
    nvim_socket = "/tmp/herdr-code-" + str(os.getuid()) + "/" + key + ".sock"
    def ready():
        response = run([NVIM, "--headless", "--server", nvim_socket, "--remote-expr",
                        "luaeval('require(\"herdr-code\").context_path')"], check=False)
        if response.returncode or not response.stdout.strip():
            return None
        path = Path(response.stdout.strip())
        if path.exists():
            if path not in paths:
                paths.append(path)
            return json.loads(path.read_text())
        return None
    return wait(ready, "persistent editor")


def lua(record, code):
    body = code if ";" in code else "return " + code
    expression = "luaeval(" + json.dumps("(function() " + body + " end)()") + ")"
    return run([NVIM, "--headless", "--server", record["nvim_socket"], "--remote-expr", expression]).stdout.strip()


def assert_checkout(record, root):
    editor = api("pane.get", {"pane_id": record["editor_pane"]})["pane"]
    assert editor["cwd"] == str(root), editor
    assert editor["foreground_cwd"] == str(root), editor
    assert lua(record, "vim.fn.getcwd()") == str(root)
    assert lua(record, "for _, win in ipairs(vim.api.nvim_list_wins()) do if vim.wo[win].winbar:find(',ab return', 1, true) then return false end end; return true") == "true", "Code still shows its instruction winbar"


def text():
    return run([TMUX, "-L", SESSION, "capture-pane", "-t", "test", "-p"]).stdout


def keys(*values):
    run([TMUX, "-L", SESSION, "send-keys", "-t", "test", *values])


def report(source, kind="codex", seq=1, state="idle", authority="test:code", session_id=None):
    api("pane.report_agent", {"pane_id": source["pane_id"], "source": authority, "agent": kind,
                            "state": state, "seq": seq, "agent_session_id": session_id})


temporary = tempfile.TemporaryDirectory(prefix="herdr-code-test-")
try:
    base = Path(temporary.name).resolve()
    root = base / "checkout with spaces"
    root.mkdir()
    (root / "sample.txt").write_text("context\nbefore\n")
    (root / "src").mkdir()
    (root / "src" / "kept.txt").write_text("nested source pane fixture\n")
    (root / "code.py").write_text("raise SystemExit('The checkout code.py must never be executed')\n")
    run(["jj", "git", "init", str(root)])
    run(["jj", "describe", "-m", "Code fixture baseline"], cwd=root)
    run(["jj", "new"], cwd=root)
    (root / "sample.txt").write_text("context\nafter\n")
    ENV["XDG_STATE_HOME"] = str(base / "state")
    ENV["XDG_CACHE_HOME"] = str(base / "cache")
    config = (PLUGIN.parents[1] / "config.toml").read_text()
    config_path = base / "herdr.toml"
    config_path.write_text(config)
    ENV["HERDR_CONFIG_PATH"] = str(config_path)
    with (base / "server.log").open("w") as log:
        server = subprocess.Popen([HERDR, "--session", SESSION, "server"], env=ENV, stdout=log, stderr=log)
        status = wait(lambda: (r.stdout if "status: running" in (r := herdr("status", check=False)).stdout else None), "server")
        address = Path(re.search(r"socket:\s*(.+)", status).group(1).strip())
        source = api("workspace.create", {"cwd": str(root), "focus": False})["root_pane"]
        workspace_label = api("workspace.get", {"workspace_id": source["workspace_id"]})["workspace"]["label"]
        assert workspace_label == root.name
        report(source)
        api("pane.report_agent_session", {"pane_id": source["pane_id"], "source": "herdr:codex", "agent": "codex",
                "agent_session_id": "00000000-0000-4000-a000-000000000001", "seq": 1})
        run([TMUX, "-L", SESSION, "new-session", "-d", "-s", "test", "-x", "180", "-y", "52",
             "exec " + shlex.quote(HERDR) + " --session " + shlex.quote(SESSION)])
        api("pane.focus", {"pane_id": source["pane_id"]})
        wait(lambda: text().strip(), "client")
        keys("-H", "01", "65")
        record = editor_record(source, root)
        wait(lambda: snapshot()["focused_pane_id"] == record["editor_pane"], "Code tab focus")
        wait(lambda: lua(record, "#vim.api.nvim_list_uis()") == "1", "single Code UI")
        assert len(snapshot()["panes"]) == 2
        tab = next(tab for tab in snapshot()["tabs"] if tab["tab_id"] != source["tab_id"])
        assert tab["label"] == "Code", tab
        assert api("tab.list", {"workspace_id": source["workspace_id"]})["tabs"][-1]["tab_id"] == tab["tab_id"], "Code was not placed last"
        evidence["initial_code_tab_is_last"] = True
        assert_checkout(record, root)
        assert lua(record, "vim.wo.winbar") == "", "Code should not reserve a top line for instructions"
        evidence["no_code_instruction_winbar"] = True
        evidence["code_host_and_neovim_use_checkout_not_plugin_directory"] = True
        assert api("workspace.get", {"workspace_id": source["workspace_id"]})["workspace"]["label"] == workspace_label, "Pinned Code replaced the workspace name with its plugin directory"
        evidence["pinned_code_preserves_automatic_workspace_name"] = True
        focus_before = snapshot()["focused_pane_id"]
        api("tab.move", {"tab_id": tab["tab_id"], "insert_index": 0})
        wait(lambda: tab_ids(source["workspace_id"])[-1] == tab["tab_id"], "Code re-pins after moving it to the start")
        assert snapshot()["focused_pane_id"] == focus_before
        wait(lambda: "Code" in text().splitlines()[0], "Code tab rendered in top bar")
        evidence["pinned_topbar_render"] = text()
        evidence["moved_code_re_pins_without_changing_focus"] = True
        evidence["actual_ctrl_a_e_opens_code_tab"] = True
        assert lua(record, "require('nvim-tree.api').tree.is_visible()") == "true"
        assert lua(record, "require('nvim-tree.core').get_cwd()") == str(root)
        lua(record, "require('nvim-tree.api').tree.focus(); return true")
        keys("/", "sample.txt", "Enter", "Enter")
        wait(lambda: lua(record, "vim.api.nvim_buf_get_name(0)") == str(root / "sample.txt"), "open file from real explorer")
        wait(lambda: "context" in text() and "after" in text(), "explorer-selected file renders")
        evidence["code_starts_with_checkout_explorer_and_opens_selected_file"] = True
        (root / "live.txt").write_text("initial\n")
        lua(record, "vim.cmd('edit live.txt'); return true")
        (root / "live.txt").write_text("agent updated this\n")
        wait(lambda: lua(record, "vim.api.nvim_buf_get_lines(vim.fn.bufnr('live.txt'),0,1,false)[1]") == "agent updated this", "live external file reload")
        evidence["external_file_edits_reload"] = True
        lua(record, "vim.cmd('edit sample.txt'); vim.api.nvim_buf_set_lines(0,0,-1,false,{'unsaved code'}); return true")
        keys(",", "a", "a")
        wait(lambda: "Comment" in text() and lua(record, "vim.api.nvim_get_mode().mode") == "c", "real tag composer")
        keys("Explain this", "Enter")
        wait(lambda: lua(record, "require('herdr-nvim.annotations').total()") == "1", "tagging through actual shortcut")
        evidence["actual_tag_shortcut_queues_code_comment"] = True
        keys("-H", "01", "65")
        wait(lambda: snapshot()["focused_pane_id"] == source["pane_id"], "one-key return")
        wait(lambda: lua(record, "#vim.api.nvim_list_uis()") == "0", "hidden editor detached")
        keys("-H", "01", "45")
        wait(lambda: "Code · Ctrl+a e returns" in text(), "real overlay rendered")
        wait(lambda: "unsaved code" in text(), "overlay shares modified buffer")
        wait(lambda: lua(record, "#vim.api.nvim_list_uis()") == "1", "single overlay UI")
        assert len(snapshot()["panes"]) == 2, "Overlay created a second editor pane"
        assert lua(record, "require('herdr-nvim.annotations').total()") == "1"
        evidence["overlay_render"] = text()
        assert_checkout(record, root)
        evidence["overlay_shares_unsaved_buffers_and_comments"] = True
        keys(",", "a", "e")
        wait(lambda: snapshot()["focused_pane_id"] == record["editor_pane"], "overlay promotes to Code tab")
        wait(lambda: "Code · Ctrl+a e returns" not in text() and "unsaved code" in text(), "popup closed and Code UI restored")
        wait(lambda: lua(record, "#vim.api.nvim_list_uis()") == "1", "single UI after promotion")
        evidence["overlay_promotes_without_second_editor"] = True
        keys("A", " - typed")
        wait(lambda: lua(record, "vim.api.nvim_get_mode().mode") == "i", "real insert mode")
        keys("-H", "01", "65")
        wait(lambda: snapshot()["focused_pane_id"] == source["pane_id"], "return while inserting")
        wait(lambda: lua(record, "#vim.api.nvim_list_uis()") == "0", "insert-mode tab detaches")
        keys("-H", "01", "45")
        wait(lambda: "Code · Ctrl+a e returns" in text(), "insert-mode overlay attaches")
        assert lua(record, "vim.api.nvim_get_mode().mode") == "i"
        keys(" - overlay", "Escape")
        wait(lambda: lua(record, "vim.api.nvim_get_mode().mode") == "n", "leave insert mode")
        assert lua(record, "vim.api.nvim_buf_get_lines(0,0,1,false)[1]") == "unsaved code - typed - overlay"
        cursor = lua(record, "vim.inspect(vim.api.nvim_win_get_cursor(0))")
        keys(",", "a", "e")
        wait(lambda: snapshot()["focused_pane_id"] == record["editor_pane"], "insert-mode editor promoted")
        wait(lambda: "Code · Ctrl+a e returns" not in text() and "unsaved code" in text(), "typed editor tab restored")
        assert lua(record, "vim.inspect(vim.api.nvim_win_get_cursor(0))") == cursor
        evidence["insert_mode_text_and_cursor_survive_switch"] = True
        for cycle in range(10):
            keys("-H", "01", "65")
            wait(lambda: snapshot()["focused_pane_id"] == source["pane_id"], "repeat return " + str(cycle))
            wait(lambda: lua(record, "#vim.api.nvim_list_uis()") == "0", "repeat detach " + str(cycle))
            keys("-H", "01", "45")
            wait(lambda: "Code · Ctrl+a e returns" in text() and "unsaved code" in text(), "repeat overlay " + str(cycle))
            assert lua(record, "#vim.api.nvim_list_uis()") == "1"
            keys(",", "a", "e")
            wait(lambda: snapshot()["focused_pane_id"] == record["editor_pane"], "repeat promotion " + str(cycle))
            wait(lambda: "Code · Ctrl+a e returns" not in text() and "unsaved code" in text(), "repeat tab " + str(cycle))
            assert lua(record, "#vim.api.nvim_list_uis()") == "1"
            assert lua(record, "require('herdr-nvim.annotations').total()") == "1"
            assert lua(record, "vim.inspect(vim.api.nvim_win_get_cursor(0))") == cursor
            assert len(snapshot()["panes"]) == 2
            assert_checkout(record, root)
        evidence["ten_switch_cycles_keep_one_ui_cursor_and_comments"] = True
        keys("-H", "01", "65")
        wait(lambda: snapshot()["focused_pane_id"] == source["pane_id"], "return before changes shortcut")
        keys("-H", "01", "72")
        wait(lambda: lua(record, "#vim.api.nvim_list_tabpages()") == "2", "CodeDiff through actual Ctrl-a r")
        wait(lambda: lua(record, "local s=require('codediff.ui.lifecycle').get_session(vim.api.nvim_get_current_tabpage()); return s and s.stored_diff_result ~= nil") == "true", "rendered inline comparison")
        keys("C-y", "C-y")
        wait(lambda: "before" in text() and "unsaved code" in text(), "real diff rendering")
        assert snapshot()["focused_pane_id"] == record["editor_pane"], "Review opened beside the agent instead of in Code"
        assert len(snapshot()["panes"]) == 2, "Review created another editor pane"
        assert lua(record, "require('codediff.ui.lifecycle').get_layout(vim.api.nvim_get_current_tabpage())") == "inline"
        assert lua(record, "require('codediff.ui.lifecycle').get_panel_view(vim.api.nvim_get_current_tabpage()).is_hidden") == "true"
        assert lua(record, "#vim.api.nvim_tabpage_list_wins(0)") == "1", "Inline review has extra columns"
        assert lua(record, "vim.api.nvim_win_get_width(0) == vim.o.columns") == "true"
        evidence["changes_render"] = text()
        evidence["actual_ctrl_a_r_opens_full_width_inline_diff_without_file_list"] = True
        keys(",", "b")
        wait(lambda: lua(record, "require('codediff.ui.lifecycle').get_panel_view(vim.api.nvim_get_current_tabpage()).is_hidden") == "false", "on-demand changed-file list")
        (root / "new-agent-file.txt").write_text("fresh external change\n")
        wait(lambda: "new-agent-file.txt" in text(), "live diff adds externally created file")
        evidence["ongoing_diff_refreshes_changed_file_list"] = True
        keys(",", "b")
        wait(lambda: lua(record, "#vim.api.nvim_tabpage_list_wins(0)") == "1", "changed-file list hides again")
        diff_page = lua(record, "vim.api.nvim_get_current_tabpage()")
        keys(",", "a", "d")
        wait(lambda: lua(record, "vim.api.nvim_get_current_tabpage()") != diff_page, "single shortcut returns to files")
        assert lua(record, "require('nvim-tree.api').tree.is_visible()") == "true"
        assert lua(record, "require('herdr-nvim.annotations').total()") == "1"
        keys(",", "a", "d")
        wait(lambda: lua(record, "vim.api.nvim_get_current_tabpage()") == diff_page, "same shortcut reuses diff")
        assert lua(record, "#vim.api.nvim_list_tabpages()") == "2"
        evidence["one_shortcut_toggles_explorer_and_shared_diff"] = True
        lua(record, "vim.api.nvim_feedkeys('q','xt',false); return true")
        assert snapshot()["focused_pane_id"] == record["editor_pane"], "Closing diff left Code tab"
        assert lua(record, "vim.bo[vim.fn.bufnr('sample.txt')].modified") == "true"
        assert (root / "sample.txt").read_text() == "context\nafter\n"
        evidence["diff_closes_to_code_without_saving"] = True
        run([TMUX, "-L", SESSION, "resize-window", "-t", "test", "-x", "90", "-y", "32"])
        wait(lambda: int(lua(record, "vim.o.columns")) < 100, "real terminal resize")
        keys(",", "a", "d")
        wait(lambda: lua(record, "#vim.api.nvim_list_tabpages()") == "2", "narrow checkout diff")
        assert lua(record, "require('codediff.ui.lifecycle').get_layout(vim.api.nvim_get_current_tabpage())") == "inline"
        wait(lambda: "unsaved" in text(), "inline diff renders modified text")
        assert lua(record, "vim.api.nvim_buf_get_lines(require('codediff.ui.lifecycle').get_session(vim.api.nvim_get_current_tabpage()).modified_bufnr,0,1,false)[1]") == "unsaved code - typed - overlay"
        evidence["narrow_diff_render"] = text()
        keys("q")
        wait(lambda: lua(record, "#vim.api.nvim_list_tabpages()") == "1", "narrow diff closes to files")
        run([TMUX, "-L", SESSION, "resize-window", "-t", "test", "-x", "180", "-y", "52"])
        wait(lambda: int(lua(record, "vim.o.columns")) >= 100, "terminal width restored")
        assert lua(record, "require('herdr-nvim.annotations').total()") == "1"
        evidence["narrow_diff_keeps_inline_default_and_comments"] = True
        other = api("tab.create", {"workspace_id": source["workspace_id"], "cwd": str(root / "src"), "focus": False})["root_pane"]
        report(other)
        count = len(snapshot()["panes"])
        invoke(other)
        wait(lambda: snapshot()["focused_pane_id"] == record["editor_pane"], "same-checkout reuse")
        def reused():
            current = editor_record(other, root)
            return current if current["source_pane"] == other["pane_id"] else None
        current = wait(reused, "new return destination recorded")
        assert current["editor_pane"] == record["editor_pane"]
        assert len(snapshot()["panes"]) == count
        assert current["source_pane"] == other["pane_id"]
        assert current["target"]["pane_id"] == source["pane_id"], "Opening from another agent retargeted comments"
        keys(",", "a", "b")
        wait(lambda: snapshot()["focused_pane_id"] == other["pane_id"], "return to most recent agent")
        evidence["shared_editor_separate_return_and_target"] = True
        invoke(other, "overlay")
        wait(lambda: "Code · Ctrl+a e returns" in text(), "second overlay")
        keys("-H", "01", "45")
        wait(lambda: "Code · Ctrl+a e returns" not in text(), "prefix dismisses popup inside Vim")
        wait(lambda: lua(record, "#vim.api.nvim_list_uis()") == "0", "overlay dismissed without quitting editor")
        evidence["overlay_prefix_dismissal"] = True
        invoke(other)
        wait(lambda: snapshot()["focused_pane_id"] == record["editor_pane"], "code reopened")
        # Capture the real companion payload, never submit to an agent.
        capture_output = base / "sent.json"
        capture = base / "capture.py"
        capture.write_text("#!/usr/bin/env python3\nimport json,sys\nfrom pathlib import Path\nPath(" + repr(str(capture_output)) + ").write_text(json.dumps({'args':sys.argv[1:],'payload':json.load(sys.stdin)}))\nprint(json.dumps({'ok':True,'target':{'pane_id':sys.argv[sys.argv.index('--target')+1],'agent':'codex'},'count':1}))\n")
        capture.chmod(0o700)
        real_binary = lua(record, "require('herdr-nvim.bridge').binary(require('herdr-nvim').config)")
        assert real_binary and real_binary != "nil", "Real herdr-nvim binary is required"
        lua(record, "require('herdr-nvim').config.binary=" + json.dumps(str(capture)) + "; return true")
        keys(",", "a", "s")
        wait(lambda: capture_output.exists() or "Send tagged code to" in text(), "recipient picker or premature send")
        assert not capture_output.exists(), "Send shortcut delivered before asking for a recipient"
        evidence["recipient_picker_render"] = text()
        lua(record, "require('herdr-nvim').send(); return true")
        assert not capture_output.exists()
        assert lua(record, "require('herdr-nvim')._inflight") == "true"
        keys("Escape")
        wait(lambda: lua(record, "require('herdr-nvim')._inflight") == "false", "cancelled recipient selection")
        assert not capture_output.exists()
        wait(lambda: "Send tagged code to" not in text(), "cancelled picker closes")
        assert lua(record, "require('herdr-nvim.annotations').total()") == "1"
        assert editor_record(other, root)["target"]["pane_id"] == source["pane_id"]
        evidence["send_cancellation_keeps_tags_and_previous_recipient"] = True
        for reply in ({"code": 1, "stdout": "", "stderr": "test list failure"},
                      {"code": 0, "stdout": json.dumps({"result": {"agents": []}}), "stderr": ""}):
            lua(record, "_G.code_list_system=vim.system; vim.system=function(args,opts,callback) if args[1]=='herdr' and args[2]=='agent' and args[3]=='list' then local response=vim.json.decode(" + json.dumps(json.dumps(reply)) + "); vim.schedule(function() callback(response) end); return {} end; return _G.code_list_system(args,opts,callback) end; require('herdr-nvim').send(); return true")
            wait(lambda: lua(record, "require('herdr-nvim')._inflight") == "false", "agent-list failure releases send")
            assert not capture_output.exists()
            assert lua(record, "require('herdr-nvim.annotations').total()") == "1"
            lua(record, "vim.system=_G.code_list_system; return true")
        evidence["empty_or_failed_agent_list_keeps_tags_and_allows_retry"] = True
        keys(",", "a", "s")
        wait(lambda: "Send tagged code to" in text(), "recipient confirmation on retry")
        assert not capture_output.exists()
        keys("Enter")
        wait(capture_output.exists, "annotation capture after recipient confirmation")
        submitted = json.loads(capture_output.read_text())
        assert submitted["args"][-2:] == ["--target", source["pane_id"]]
        assert submitted["payload"]["comments"][0]["modified"] is True
        capture_output.unlink()
        wait(lambda: lua(record, "require('herdr-nvim')._inflight") == "false", "first tag submission completes")
        lua(record, "vim.cmd('edit selection.txt'); vim.api.nvim_buf_set_lines(0,0,-1,false,{'selected first line','selected second line','outside selection'}); vim.api.nvim_win_set_cursor(0,{1,0}); return true")
        keys("V", "j", ",", "a", "a")
        wait(lambda: "Comment" in text() and lua(record, "vim.api.nvim_get_mode().mode") == "c", "visual-selection tag composer")
        keys("Explain selected lines", "Enter")
        wait(lambda: lua(record, "require('herdr-nvim.annotations').total()") == "1", "selected lines tagged")
        keys(",", "a", "S")
        wait(lambda: "Send tagged code to" in text(), "legacy send shortcut also asks recipient")
        assert not capture_output.exists()
        keys("'" + other["pane_id"])
        wait(lambda: "1/2" in text(), "exact pane filter leaves one recipient")
        keys("Enter")
        wait(capture_output.exists, "selected-code tag capture after filtering recipient")
        assert json.loads(capture_output.read_text())["args"][-2:] == ["--target", other["pane_id"]]
        evidence["legacy_send_requires_choice_and_can_filter_another_recipient"] = True
        selected = json.loads(capture_output.read_text())["payload"]["comments"][0]
        assert selected["line"] == 1 and selected["end_line"] == 2, selected
        assert selected["code"] == "selected first line\nselected second line", selected
        assert selected["modified"] is True
        evidence["visual_tags_send_exact_selected_lines_capture_only"] = True
        capture_output.unlink()
        wait(lambda: lua(record, "require('herdr-nvim')._inflight") == "false", "selection submission completes")
        lua(record, "vim.cmd('buffer sample.txt'); require('herdr-nvim.annotations').add(0,0,0,'Confirm last recipient'); return true")
        keys(":HerdrSend", "Enter")
        wait(lambda: "Send tagged code to" in text() and "2/2" in text(), "send command offers both recipients")
        assert not capture_output.exists()
        evidence["quick_default_picker_render"] = text()
        keys("Enter")
        wait(capture_output.exists, "last-recipient quick default capture")
        assert json.loads(capture_output.read_text())["args"][-2:] == ["--target", other["pane_id"]]
        evidence["send_command_confirms_last_recipient_first"] = True
        capture_output.unlink()
        wait(lambda: lua(record, "require('herdr-nvim')._inflight") == "false", "quick-default submission completes")
        lua(record, "require('herdr-nvim').ask({message='Explain this code'}); return true")
        wait(capture_output.exists, "question capture")
        assert json.loads(capture_output.read_text())["args"][-2:] == ["--target", other["pane_id"]]
        evidence["questions_and_comments_share_explicit_target_capture_only"] = True
        capture_output.unlink()
        keys(",", "a", "t")
        wait(lambda: "Choose default agent" in text(), "choose default without sending")
        keys("'" + source["pane_id"])
        wait(lambda: "1/2" in text(), "default picker filters source")
        keys("Enter")
        wait(lambda: editor_record(other, root)["target"]["pane_id"] == source["pane_id"], "source chosen for preflight checks")
        original_session_id = record["target"]["session"]["value"]
        report(source, seq=2, state="blocked", authority="herdr:codex", session_id=original_session_id)
        wait(lambda: api("pane.get", {"pane_id": source["pane_id"]})["pane"]["agent_status"] == "blocked", "actual blocked agent metadata")
        before_delivery = herdr("pane", "read", source["pane_id"], "--source", "recent").stdout
        lua(record, "_G.code_blocked_messages={}; vim.notify=function(message) table.insert(_G.code_blocked_messages,message) end; require('herdr-nvim').config.binary=" + json.dumps(real_binary) + "; require('herdr-nvim.annotations').add(0,0,0,'Keep blocked comment'); require('herdr-nvim').send(); return true")
        wait(lambda: "Send tagged code to" in text(), "blocked target still requires explicit choice")
        keys("Enter")
        wait(lambda: lua(record, "require('herdr-nvim')._inflight") == "false", "real blocked comment preflight")
        assert lua(record, "require('herdr-nvim.annotations').total()") == "1"
        lua(record, "require('herdr-nvim').ask({message='Keep blocked question'}); return true")
        wait(lambda: lua(record, "require('herdr-nvim')._inflight") == "false", "real blocked question preflight")
        assert lua(record, "require('herdr-nvim.ask').draft()") == "Keep blocked question"
        evidence["blocked_preflight_diagnostics"] = lua(record, "table.concat(_G.code_blocked_messages,'|')")
        assert "blocked waiting" in evidence["blocked_preflight_diagnostics"], evidence["blocked_preflight_diagnostics"]
        assert herdr("pane", "read", source["pane_id"], "--source", "recent").stdout == before_delivery
        evidence["real_companion_blocks_questions_and_comments_without_terminal_input"] = True
        report(source, seq=3, authority="herdr:codex", session_id=original_session_id)
        lua(record, "require('herdr-nvim').config.binary=" + json.dumps(str(capture)) + "; return true")
        lua(record, "_G.code_original_select=vim.ui.select; vim.ui.select=function(items,opts,callback) _G.code_pick_items=items; _G.code_pick_callback=callback end; require('herdr-nvim').send(); return true")
        wait(lambda: lua(record, "type(_G.code_pick_callback)") == "function", "hold recipient choice before session replacement")
        api("pane.report_agent_session", {"pane_id": source["pane_id"], "source": "herdr:codex", "agent": "codex",
                "agent_session_id": "00000000-0000-4000-a000-000000000002", "session_start_source": "resume", "seq": 4})
        wait(lambda: api("pane.get", {"pane_id": source["pane_id"]})["pane"]["agent_session"] != record["target"]["session"], "actual replacement session")
        lua(record, "_G.code_pick_callback(_G.code_pick_items[1]); vim.ui.select=_G.code_original_select; return true")
        wait(lambda: lua(record, "require('herdr-nvim')._inflight") == "false", "real replaced-session comment rejection")
        assert not capture_output.exists()
        assert lua(record, "require('herdr-nvim.annotations').total()") == "1"
        lua(record, "require('herdr-nvim').ask({message='Keep replaced-session question'}); return true")
        wait(lambda: lua(record, "require('herdr-nvim')._inflight") == "false", "real replaced-session question rejection")
        assert not capture_output.exists()
        assert lua(record, "require('herdr-nvim.ask').draft()") == "Keep replaced-session question"
        evidence["actual_replaced_session_blocks_both_senders_preserves_drafts"] = True
        lua(record, "require('herdr-nvim.annotations').clear(); return true")
        # Yuke reports its session as a token, not always as agent_session.
        yuke = api("pane.get", {"pane_id": source["pane_id"]})["pane"]
        yuke.update(agent="yuke", tokens={"yuke_session_id": "replacement"})
        context_path = paths[0]
        saved = json.loads(context_path.read_text())
        saved["target"] = dict(saved["target"], agent="yuke", session=None, yuke_session_id="original")
        context_path.write_text(json.dumps(saved))
        lua(record, "_G.code_original_choose=require('herdr-code').choose_target; require('herdr-code').choose_target=function(done) done(vim.json.decode(" + json.dumps(json.dumps(saved["target"])) + ")) end; _G.code_test_messages={}; vim.notify=function(message) table.insert(_G.code_test_messages,message) end; local original=vim.system; _G.code_original_system=original; local response=" + json.dumps(json.dumps({"result": {"pane": yuke}})) + "; vim.system=function(args,opts,callback) if args[1]=='herdr' and args[2]=='pane' and args[3]=='get' then vim.schedule(function() callback({code=0,stdout=response,stderr=''}) end); return {} end; return original(args,opts,callback) end; require('herdr-code').refresh_context(); require('herdr-nvim.annotations').add(0,0,0,'Keep this comment'); require('herdr-nvim').send(); return true")
        wait(lambda: lua(record, "require('herdr-nvim')._inflight") == "false", "stale Yuke rejection")
        assert not capture_output.exists()
        assert lua(record, "require('herdr-nvim.annotations').total()") == "1"
        lua(record, "require('herdr-nvim').ask({message='Keep this question'}); return true")
        wait(lambda: lua(record, "require('herdr-nvim')._inflight") == "false", "stale question rejection")
        assert not capture_output.exists()
        assert lua(record, "require('herdr-nvim.ask').draft()") == "Keep this question"
        evidence["changed_yuke_session_blocks_both_senders_preserves_drafts"] = "simulated metadata; real adapters and queues"
        lua(record, "vim.system=_G.code_original_system; require('herdr-code').choose_target=_G.code_original_choose; vim.ui.select=function(items,opts,callback) for _,item in ipairs(items) do if item.pane_id==" + json.dumps(other["pane_id"]) + " then callback(item); return end end end; require('herdr-code').choose_target(); return true")
        wait(lambda: json.loads(context_path.read_text())["target"]["pane_id"] == other["pane_id"], "explicit recipient selection")
        wait(lambda: lua(record, "require('herdr-nvim.ask').target().pane_id") == other["pane_id"], "editor target refreshed")
        lua(record, "require('herdr-nvim').send(); return true")
        wait(capture_output.exists, "retargeted annotation capture")
        assert json.loads(capture_output.read_text())["args"][-2:] == ["--target", other["pane_id"]]
        evidence["explicit_picker_retargets_comments"] = True
        lua(record, "vim.api.nvim_buf_set_lines(vim.fn.bufnr('sample.txt'),0,-1,false,{'recover this unsaved buffer'}); return true")
        editor = api("pane.get", {"pane_id": record["editor_pane"]})["pane"]
        api("tab.close", {"tab_id": editor["tab_id"]})
        wait(lambda: not Path(record["nvim_socket"]).exists(), "owned editor shuts down with its tab")
        recovery_path = Path(record["recovery"])
        wait(lambda: recovery_path.exists() and 'recover this unsaved buffer' in recovery_path.read_text(), "unsaved recovery written")
        assert (root / "sample.txt").read_text() == "context\nafter\n"
        invoke(other)
        record = editor_record(other, root)
        wait(lambda: lua(record, "vim.bo[vim.fn.bufnr('sample.txt')].modified") == "true", "recovered buffer marked unsaved")
        assert lua(record, "vim.api.nvim_buf_get_lines(vim.fn.bufnr('sample.txt'),0,1,false)[1]") == "recover this unsaved buffer"
        evidence["tab_close_stops_editor_recovers_unsaved_buffers_without_saving"] = True
        lua(record, "vim.cmd('edit immediate-reopen.txt'); vim.api.nvim_buf_set_lines(0,0,-1,false,{'keep across immediate reopen'}); return true")
        keys("-H", "01", "65")
        wait(lambda: snapshot()["focused_pane_id"] == other["pane_id"], "return before immediate reopen overlay")
        invoke(other, "overlay")
        wait(lambda: "Code · Ctrl+a e returns" in text(), "overlay before owner close")
        closing = record
        closing_pane = api("pane.get", {"pane_id": closing["editor_pane"]})["pane"]
        api("tab.close", {"tab_id": closing_pane["tab_id"]})
        invoke(other)
        record = wait(lambda: (current if (current := editor_record(other, root))["editor_pane"] != closing["editor_pane"] else None), "immediately reopened editor")
        wait(lambda: snapshot()["focused_pane_id"] == record["editor_pane"], "immediately reopened tab focus")
        wait(lambda: lua(record, "#vim.api.nvim_list_uis()") == "1", "immediately reopened UI")
        assert lua(record, "vim.api.nvim_buf_get_lines(vim.fn.bufnr('immediate-reopen.txt'),0,1,false)[1]") == "keep across immediate reopen"
        assert lua(record, "vim.bo[vim.fn.bufnr('immediate-reopen.txt')].modified") == "true"
        assert not (root / "immediate-reopen.txt").exists()
        evidence["immediate_overlay_owner_close_and_reopen_recovers_buffer"] = True
        different = api("workspace.create", {"cwd": str(root / "src"), "label": "Agent Tests independent Code", "focus": False})["root_pane"]
        invoke(different)
        independent = editor_record(different, root)
        wait(lambda: lua(independent, "#vim.api.nvim_list_uis()") == "1", "nested-source editor attached")
        assert_checkout(independent, root)
        assert api("workspace.get", {"workspace_id": different["workspace_id"]})["workspace"]["label"] == "Agent Tests independent Code"
        evidence["nested_source_opens_checkout_root_and_preserves_explicit_workspace_name"] = True
        assert independent["editor_pane"] != record["editor_pane"]
        assert independent["nvim_socket"] != record["nvim_socket"]
        evidence["same_checkout_in_another_workspace_has_separate_editor"] = True
        lua(record, "require('herdr-nvim.annotations').add(vim.fn.bufnr('sample.txt'),0,0,'original checkout tag'); return true")
        linked = base / "linked-jj"
        run(["jj", "workspace", "add", str(linked), "-r", "@-"], cwd=root)
        assert (linked / ".jj").exists() and not (linked / ".git").exists()
        linked_source = api("tab.create", {"workspace_id": source["workspace_id"], "cwd": str(linked), "focus": False})["root_pane"]
        invoke(linked_source)
        linked_record = editor_record(linked_source, linked)
        wait(lambda: lua(linked_record, "#vim.api.nvim_list_uis()") == "1", "linked jj Code UI")
        assert linked_record["editor_pane"] != record["editor_pane"]
        assert linked_record["target"] is None
        assert editor_record(other, root)["target"]["pane_id"] == other["pane_id"]
        assert lua(linked_record, "require('herdr-nvim.annotations').total()") == "0"
        lua(linked_record, "vim.cmd('edit sample.txt'); vim.api.nvim_buf_set_lines(0,0,-1,false,{'independent worktree text'}); require('herdr-nvim.annotations').add(0,0,0,'linked checkout tag'); return true")
        assert lua(record, "vim.api.nvim_buf_get_lines(vim.fn.bufnr('sample.txt'),0,1,false)[1]") == "recover this unsaved buffer"
        assert lua(record, "require('herdr-nvim.annotations').list()[1].text") == "original checkout tag"
        assert lua(linked_record, "require('herdr-nvim.annotations').list()[1].text") == "linked checkout tag"
        assert (root / "sample.txt").read_text() == "context\nafter\n"
        assert (linked / "sample.txt").read_text() == "context\nbefore\n"
        evidence["worktrees_keep_buffers_comments_and_recipients_separate"] = True
        root_tab = api("pane.get", {"pane_id": record["editor_pane"]})["pane"]["tab_id"]
        linked_tab = api("pane.get", {"pane_id": linked_record["editor_pane"]})["pane"]["tab_id"]
        wait(lambda: tab_ids(source["workspace_id"])[-2:] == [root_tab, linked_tab], "both worktree Code tabs grouped last")
        assert_checkout(record, root)
        assert_checkout(linked_record, linked)
        wait(lambda: api("workspace.get", {"workspace_id": source["workspace_id"]})["workspace"]["label"] == workspace_label, "Code selection must not replace the first regular checkout name")
        evidence["multiple_worktree_code_tabs_use_their_own_checkout_directories"] = True
        spoof = api("tab.create", {"workspace_id": source["workspace_id"], "cwd": str(root),
                                   "label": "Code", "focus": False})["root_pane"]
        api("pane.focus", {"pane_id": other["pane_id"]})
        moved = api("tab.move", {"tab_id": other["tab_id"], "insert_index": 0})["tabs"]
        intended_normals = [item["tab_id"] for item in moved if item["tab_id"] not in (root_tab, linked_tab)]
        wait(lambda: tab_ids(source["workspace_id"]) == [*intended_normals, root_tab, linked_tab], "Code block follows ordinary tabs")
        assert snapshot()["focused_pane_id"] == other["pane_id"]
        api("tab.move", {"tab_id": root_tab, "insert_index": 0})
        wait(lambda: tab_ids(source["workspace_id"]) == [*intended_normals, root_tab, linked_tab], "dragged Code restores the last group")
        assert snapshot()["focused_pane_id"] == other["pane_id"]
        assert spoof["tab_id"] in intended_normals, "A matching Code label was treated as plugin-owned"
        api("tab.focus", {"tab_id": root_tab})
        wait(lambda: tab_ids(source["workspace_id"]) == [*intended_normals, root_tab, linked_tab], "selecting Code preserves its group order")
        assert snapshot()["focused_pane_id"] == record["editor_pane"]
        wait(lambda: api("workspace.get", {"workspace_id": source["workspace_id"]})["workspace"]["label"] == "src", "workspace name follows the first regular tab, not Code")
        assert_checkout(record, root)
        invoke(linked_source)
        wait(lambda: tab_ids(source["workspace_id"]) == [*intended_normals, root_tab, linked_tab], "reopening Code preserves its group order")
        wait(lambda: snapshot()["focused_pane_id"] == linked_record["editor_pane"], "selected worktree editor focused")
        assert editor_record(linked_source, linked)["editor_pane"] == linked_record["editor_pane"]
        assert_checkout(linked_record, linked)
        wait(lambda: api("workspace.get", {"workspace_id": source["workspace_id"]})["workspace"]["label"] == "src", "reopening Code preserves the first regular tab name")
        invoke(linked_source, "overlay")
        wait(lambda: "Code · Ctrl+a e returns" in text(), "linked checkout overlay")
        wait(lambda: lua(linked_record, "#vim.api.nvim_list_uis()") == "1", "linked overlay attached")
        assert_checkout(linked_record, linked)
        assert lua(linked_record, "vim.api.nvim_buf_get_lines(vim.fn.bufnr('sample.txt'),0,1,false)[1]") == "independent worktree text"
        keys(",", "a", "e")
        wait(lambda: "Code · Ctrl+a e returns" not in text(), "linked overlay promotes to tab")
        wait(lambda: lua(linked_record, "#vim.api.nvim_list_uis()") == "1", "linked tab reattaches")
        assert_checkout(linked_record, linked)
        evidence["linked_worktree_overlay_and_tab_keep_checkout_cwd"] = True
        assert lua(record, "require('herdr-nvim.annotations').list()[1].text") == "original checkout tag"
        assert lua(linked_record, "require('herdr-nvim.annotations').list()[1].text") == "linked checkout tag"
        assert lua(record, "vim.api.nvim_buf_get_lines(vim.fn.bufnr('sample.txt'),0,1,false)[1]") == "recover this unsaved buffer"
        assert lua(linked_record, "vim.api.nvim_buf_get_lines(vim.fn.bufnr('sample.txt'),0,1,false)[1]") == "independent worktree text"
        assert editor_record(other, root)["target"]["pane_id"] == other["pane_id"]
        assert editor_record(linked_source, linked)["target"] is None
        independent_tab = api("pane.get", {"pane_id": independent["editor_pane"]})["pane"]["tab_id"]
        assert tab_ids(different["workspace_id"])[-1] == independent_tab
        evidence["worktree_code_tabs_pin_last_and_preserve_other_tab_order_and_state"] = True
        evidence["ordinary_code_named_tab_is_not_pinned"] = True
        evidence["multi_worktree_pinned_topbar_render"] = text()
        lua(linked_record, "_G.linked_messages={}; vim.notify=function(message) table.insert(_G.linked_messages,message) end; require('herdr-code').changes(); return true")
        assert "Git-backed" in lua(linked_record, "_G.linked_messages[1]")
        assert lua(linked_record, "#vim.api.nvim_list_tabpages()") == "1"
        evidence["non_colocated_jj_supports_code_reports_diff_limit"] = True
        lua(linked_record, "vim.cmd('edit orphan.txt'); vim.api.nvim_buf_set_lines(0,0,-1,false,{'survive owner loss'}); return true")
        linked_record = editor_record(linked_source, linked)
        os.kill(linked_record["host_pid"], signal.SIGKILL)
        wait(lambda: not Path(linked_record["nvim_socket"]).exists(), "editor stops after abrupt owner death")
        wait(lambda: 'survive owner loss' in Path(linked_record["recovery"]).read_text(), "owner-loss buffer recovery")
        evidence["abrupt_owner_death_stops_daemon_preserves_buffer"] = True
        evidence["ok"] = True
finally:
    if address:
        evidence["plugin_logs"] = herdr("plugin", "log", "list", "--plugin", "david.code", "--limit", "12", check=False).stdout
        evidence["pane_diagnostics"] = [herdr("pane", "read", item["pane_id"], "--source", "recent", check=False).stdout for item in snapshot()["panes"]]
        for directory in (base, Path.home() / ".config/herdr/sessions" / SESSION):
            for file in directory.rglob("code-*.log"):
                evidence["startup_log"] = file.read_text()
        if record:
            recovery = Path(record["recovery"])
            evidence["recovery_diagnostics"] = recovery.read_text() if recovery.exists() else "missing"
            try:
                evidence["last_render"] = text()
                evidence["editor_log"] = paths[0].with_suffix(".log").read_text()
            except Exception:
                pass
    owned_sockets = [json.loads(path.read_text())["nvim_socket"] for path in paths]
    run([TMUX, "-L", SESSION, "kill-server"], check=False)
    if address:
        herdr("plugin", "action", "invoke", "uninstall-refresh", "--plugin", "david.workspaces", check=False)
        herdr("session", "stop", SESSION, check=False)
        herdr("session", "delete", SESSION, check=False)
    if server:
        try:
            server.wait(timeout=8)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait()
    try:
        wait(lambda: not any(owned in run(["ps", "-axo", "args="]).stdout for owned in owned_sockets), "private Code daemons stop with session")
        evidence["no_test_daemons_left_after_session_stop"] = True
    except AssertionError:
        evidence["no_test_daemons_left_after_session_stop"] = False
        evidence["shutdown_logs"] = {str(path): path.with_suffix(".log").read_text() for path in paths}
        evidence["survivors_diagnostics"] = [line for line in run(["ps", "-axo", "pid,ppid,args="]).stdout.splitlines() if any(owned in line for owned in owned_sockets)]
    for path in paths:
        for suffix in (".json", ".lock", ".log", ".recovery"):
            path.with_suffix(suffix).unlink(missing_ok=True)
    temporary.cleanup()
    artifact = Path(os.environ.get("HERDR_CODE_TEST_ARTIFACT", "/tmp/herdr-code-integration-result.json"))
    artifact.write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps({k: v for k, v in evidence.items() if not k.endswith(("render", "log", "logs", "diagnostics"))}, indent=2))
    print("Artifact: " + str(artifact))
    assert evidence["no_test_daemons_left_after_session_stop"], "Code daemons survived session shutdown"
