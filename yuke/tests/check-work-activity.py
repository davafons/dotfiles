#!/usr/bin/env python3
"""Drive work ownership, Markdown, scrolling and two-tab navigation in a private native terminal."""
import argparse
import json
import os
from pathlib import Path
import shlex
import shutil
import socketserver
import subprocess
import tempfile
import threading
import time
import uuid

PROBE = '''
import { client, env, fs } from "yuke";
import { currentPane, Session, showSession } from "yuke:session";
export default function(ctx) {
  const tui = ctx.get("tui");
  if (!tui) return;
  if (tui.command.available("project-work:checkpoint")) throw Error("retired checkpoint command is still registered");
  let targetPin = null;
  ctx.own(() => targetPin?.release());
  tui.command.add("fixture", {desc: "Create an empty fixture session", slash: true, run: () => {
    void (async () => {
      const pane = currentPane();
      const catalog = await client.catalogList(null);
      pane.session.setModel(catalog.models.find(model => model.provider === "work-test"), "");
      const id = await pane.session.startChat(null, pane.composer);
      if (env.get("WORK_HOLDER") === "1") await client.request("session.record_command", {
        session_id:id, command:{command:"native-owner-fixture",exit_code:0}, output:"Recorded fixture only. No process or model request."
      });
      const target = await client.sessionCreate({workspace_path: (await client.sessionGet(id)).session.root, model: "work-test/model"});
      targetPin = new Session();
      if (!targetPin.open(target.session.id)) throw Error("cannot pin native owner fixture");
      await fs.writeFile(ctx.root + (env.get("WORK_HOLDER") === "1" ? "/holder-session.json" : "/session.json"), JSON.stringify({id, target: target.session.id}));
    })().catch(error => ctx.print("FIXTURE_ERROR", String(error)));
  }});
  ctx.on("chat.strip", () => [{text:"Queued-input fixture row", group:"UIDim"}]);
  tui.command.add("fixture-switch", {desc:"Switch only fixture chats", slash:true, args:true, run:(target) => {
    void (async () => {
      const fixture = JSON.parse(await fs.readFile(ctx.root + "/session.json"));
      const pane = currentPane();
      if (!pane || pane.composer.text) throw Error("fixture switch must not replace a draft");
      showSession(pane, target === "source" ? fixture.id : fixture.target);
    })().catch(error => ctx.print("FIXTURE_ERROR", String(error)));
  }});
  tui.command.add("who", {desc: "Record the current fixture session", slash: true, run: () => {
    void fs.writeFile(ctx.root + "/current.json", JSON.stringify(currentPane()?.session.sessionId));
  }});
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--profile", type=Path, default=Path(__file__).resolve().parents[1] / ".config/yuke")
    args = parser.parse_args()
    binary = args.binary.resolve(strict=True)
    root = Path(tempfile.mkdtemp(prefix="yw-", dir="/tmp")).resolve()
    root.chmod(0o700)
    profile = root / "config/yuke"
    source = args.profile.resolve(strict=True)
    shutil.copytree(source, profile, ignore=shutil.ignore_patterns("providers.json*", "*.key", ".env", "__pycache__", "yuke.d.ts", "yuke-modules.d.ts", "yuke.jsconfig.json"))
    for name in ("home", "work", "data", "state", "cache"):
        (root / name).mkdir()
    (profile / "providers.json").write_text(json.dumps({"providers": [{"id": "work-test", "base_url": "http://127.0.0.1:1/v1", "endpoints": [{"protocol": "openai_chat"}], "models": [{"id": "model", "upstream_id": "model", "flags": {"supports_tools": True}}]}]}))
    (profile / "providers.json").chmod(0o600)
    probe = profile / "probe"
    probe.mkdir()
    (probe / "index.js").write_text(PROBE)
    (probe / "plugin.json").write_text(json.dumps({"name": "work-probe", "extensions": {"sh.yuke": {"entry": "./index.js", "uses": ["tui"]}}}))
    config = json.loads((profile / "config.json").read_text())
    config["plugins"].append("./probe")
    (profile / "config.json").write_text(json.dumps(config))
    (root / "bin").mkdir()
    github_fixture = root / "bin/gh"
    github_fixture.write_text("#!" + shutil.which("python3") + "\n" + r'''import json, sys
from pathlib import Path
args = sys.argv[1:]
with (Path(__file__).resolve().parents[1] / "gh-calls.jsonl").open("a") as log:
    log.write(json.dumps(args) + "\n")
if args[:2] == ["repo", "view"]:
    print(json.dumps({"nameWithOwner":"fixture/work", "url":"https://github.com/fixture/work"}))
else:
    assert args[:2] == ["api", "graphql"], args
    query = next(value[6:] for value in args if value.startswith("query="))
    assert query.startswith("query("), "only read-only queries are allowed"
    pulls = "pullRequests(" in query or "pullRequest(" in query
    raw = {"number":23 if pulls else 17,"title":"FIXTURE_PR_REVIEW" if pulls else "FIXTURE_GITHUB_ISSUE",
           "url":"https://github.com/fixture/work/" + ("pull/23" if pulls else "issues/17"),
           "state":"OPEN","updatedAt":"2026-10-17T00:00:00Z","author":{"login":"fixture"},"labels":{"nodes":[]},
           "body":"## Fixture GitHub body","isDraft":False,"reviewDecision":"APPROVED","headRefName":"feature","baseRefName":"main",
           "statusCheckRollup":{"state":"SUCCESS","contexts":{"nodes":[{"name":"Fixture CI","conclusion":"SUCCESS"}],"pageInfo":{"hasNextPage":False}}}}
    if "number=" in " ".join(args):
        reply = {"pullRequest" if pulls else "issue":raw}
    else:
        reply = {"pullRequests" if pulls else "issues":{"totalCount":1,"nodes":[raw],"pageInfo":{"endCursor":"","hasNextPage":False}}}
    print(json.dumps({"data":{"repository":reply}}))
''')
    github_fixture.chmod(0o700)
    foreign = "1" * 32
    creator = "2" * 32
    reported = "working"
    calls = []

    class Herdr(socketserver.StreamRequestHandler):
        def handle(self):
            request = json.loads(self.rfile.readline())
            calls.append(request)
            result = {"type": "ok"}
            if request["method"] == "pane.list":
                result = {"type": "pane_list", "panes": [{"pane_id": "foreign", "agent": "yuke", "agent_status": reported, "tokens": {"yuke_session_id": foreign, "shortcut_number": "7", "summary": "Remote app validation"}}]}
            self.wfile.write((json.dumps({"id": request["id"], "result": result}) + "\n").encode())

    server = socketserver.ThreadingUnixStreamServer(str(root / "herdr.sock"), Herdr)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    env = {"PATH": str(root / "bin") + os.pathsep + os.environ["PATH"], "HOME": str(root / "home"), "TERM": "xterm-256color", "YUKE_APPNAME": "yuke", "HERDR_ENV": "1", "HERDR_SOCKET_PATH": str(root / "herdr.sock"), "HERDR_PANE_ID": "fixture"}
    for name in ("config", "data", "state", "cache"):
        env["XDG_" + name.upper() + "_HOME"] = str(root / name)
    database = root / "state/yuke/work/work.sqlite3"

    def store(action, session=creator, **values):
        request = dict(action=action, api_version=2, root=str(root / "work"), session=session, **values)
        result = subprocess.check_output(["python3", str(profile / "plugins/project-work-store.py"), str(database), json.dumps(request)], env=env, text=True)
        return json.loads(result)

    for index in range(12):
        store("task", title=f"DEFERRED_{index:02}", status="later", notes="An independently claimable task.")
    task = store("task", title="LIVE_WORK_FIXTURE", status="later", notes="## Readable notes\n\n- **Bold item** with `cargo test`.\n- Second item.\n\n> Verification is not completion.\n\n" + "\n\n".join(f"Paragraph {i}. Keep this task now when the linked agent becomes idle." for i in range(24)))
    store("claim", session=foreign, id=task["id"], version=task["version"])
    saved = store("get", id=task["id"])["task"]
    if saved["status"] != "now":
        store("task", session=foreign, id=task["id"], version=saved["version"], title=saved["title"], status="now", notes=saved["notes"])
    store("message", session=creator, id=task["id"], body="## Coordination\n\n- Review my separate task.")
    store("task", title="COMPLETED_TASK_FIXTURE", status="done", notes="Completed tasks remain accessible by mouse.")
    socket = "yuke-work-" + uuid.uuid4().hex[:10]
    captures = []
    pane_pid = None
    holder_pid = None

    def mux(*args):
        return subprocess.check_output(["tmux", "-L", socket, *args], text=True)

    def screen():
        return mux("capture-pane", "-p", "-t", "work")

    def wait(condition, label):
        end = time.monotonic() + 15
        while time.monotonic() < end:
            if condition():
                captures.append(label + "\n" + screen())
                return
            time.sleep(0.05)
        raise AssertionError(label + "\n" + screen())

    def send(*keys):
        mux("send-keys", "-t", "work", *keys)

    def task_read():
        return store("get", id=task["id"])["task"]

    try:
        command = shlex.join(["env", "-i", *(f"{k}={v}" for k, v in env.items()), str(binary)])
        mux("new-session", "-d", "-x", "160", "-y", "45", "-s", "work", "-n", "Agent Tests work activity", "-c", str(root / "work"), command)
        pane_pid = int(mux("display-message", "-p", "-t", "work", "#{pane_pid}").strip())
        wait(lambda: "Project tasks" in screen() and "Search chats" in screen(), "dashboard entries loaded")
        send("/work", "Enter")
        wait(lambda: "LIVE_WORK_FIXTURE" in screen() and "working · Herdr" in screen(), "reported owner activity")
        assert "Agent 7 · Remote app validation" in screen(), "owner card lacks real agent number and chat summary"
        assert "1 assigned task · One task per session" in screen(), "assignment count is not based on distinct owner chats"
        assert "d Show done" not in screen() and "Show done" in screen(), "done visibility control still advertises a hotkey"
        send("d")
        for label, visible in (("Show done", True), ("Hide done", False)):
            rendered = screen().splitlines()
            control_row = next(index for index, line in enumerate(rendered) if label in line)
            control_col = rendered[control_row].index(label) + 1
            mux("send-keys", "-t", "work", "-l", f"\x1b[<0;{control_col};{control_row + 1}M\x1b[<0;{control_col};{control_row + 1}m")
            wait(lambda: ("COMPLETED_TASK_FIXTURE" in screen()) == visible, label + " remains clickable without a hotkey")

        assert "1 Board" in screen() and "2 GitHub" in screen(), "work must have only board and GitHub tabs"
        assert not any(label in screen() for label in ("Project context", "Handoffs", "Checkpoint", "Shared goal"))
        send("2")
        wait(lambda: "FIXTURE_GITHUB_ISSUE" in screen() and "Fixture GitHub body" in screen(), "second tab opens GitHub issue details")
        send("v")
        wait(lambda: "FIXTURE_PR_REVIEW" in screen() and "Fixture CI" in screen() and "APPROVED" in screen(), "PR review and CI remain available")
        send("Tab")
        wait(lambda: "LIVE_WORK_FIXTURE" in screen(), "Tab wraps to the task board")
        send("BTab")
        wait(lambda: "FIXTURE_PR_REVIEW" in screen(), "Shift-Tab wraps to GitHub")
        send("1")
        wait(lambda: "LIVE_WORK_FIXTURE" in screen(), "1 returns to the task board")
        before = screen()
        wait(lambda: screen() != before, "moving indicator")
        reported = "idle"
        wait(lambda: "idle · Herdr" in screen(), "remote idle updates live")
        assert task_read()["status"] == "now", "idle marked the task done"
        assert task_read()["owner_session"] == foreign, "idle released the owner"
        reported = "blocked"
        wait(lambda: "blocked · Herdr" in screen(), "remote blocked updates live")
        send("Enter")
        wait(lambda: "TASK ACTIONS" in screen() and "Readable notes" in screen(), "Markdown inspector and right action column")
        rendered = screen()
        assert "**Bold item**" not in rendered and "`cargo test`" not in rendered, rendered
        assert "Bold item" in rendered and "cargo test" in rendered, rendered
        assert rendered.index("TASK ACTIONS") > rendered.index("SELECTED TASK"), rendered
        styled = mux("capture-pane", "-e", "-p", "-t", "work")
        (root / "markdown-styled.txt").write_text(styled)
        assert "\x1b[" in styled, "terminal capture lacks styled output"
        send("PageDown")
        wait(lambda: "Paragraph 8" in screen() or "Paragraph 9" in screen() or "Paragraph 10" in screen(), "details scroll without moving the task")
        send("Escape")
        wait(lambda: "TASK ACTIONS" not in screen(), "return from inspector to board")
        send("l")
        wait(lambda: "1-4/12 ↓" in screen(), "viewport describes visible cards, not the loaded page")
        empty_header = next(line for line in screen().splitlines() if "Later (12)" in line)
        assert empty_header.count("▸") == 3, empty_header
        assert empty_header.index("Later (12)") > 60, "empty rails did not yield enough space to populated columns"
        send("z")
        wait(lambda: "DEFERRED_" not in screen().split("SELECTED TASK")[0], "selected populated column collapses")
        folded_header = next(line for line in screen().splitlines() if "Now (1)" in line)
        rail_col = folded_header.index("▸") + 1
        assert rail_col > 140, "folded columns occupy more than four cells each"
        mux("send-keys", "-t", "work", "-l", f"\x1b[<65;{rail_col};11M")
        wait(lambda: "DEFERRED_" in screen().split("SELECTED TASK")[0], "wheel temporarily previews a folded column")
        send("h")
        wait(lambda: "DEFERRED_" not in screen().split("SELECTED TASK")[0], "leaving a preview restores its collapsed rail")
        send("l", "j")
        wait(lambda: "DEFERRED_" in screen().split("SELECTED TASK")[0], "keyboard browsing temporarily previews the folded column")
        send("z", "h")
        wait(lambda: "DEFERRED_" in screen().split("SELECTED TASK")[0] and "> LIVE_WORK_FIXTURE" in screen(), "explicit expansion stays pinned while another column is selected")
        send("l", "k", "k", "k", "k", "k")
        wait(lambda: "1-4/12 ↓" in screen(), "pinned column preserves normal task navigation")
        send("j", "j", "j", "j")
        wait(lambda: "↑ 2-5/12 ↓" in screen(), "within-page scroll range")
        send("j")
        wait(lambda: "↑ 6-9/12 ↓" in screen(), "cross-page keyboard scroll")
        send("n")
        wait(lambda: "↑ 11-12/12 · end" in screen(), "last page end marker")
        send("h")
        reported = "working"
        wait(lambda: "working · Herdr" in screen(), "owner resumes working")
        lines = screen().splitlines()
        row = next(index for index, line in enumerate(lines) if line.startswith("> LIVE_WORK_FIXTURE"))
        mux("send-keys", "-t", "work", "-l", f"\x1b[<0;3;{row + 1}M\x1b[<0;3;{row + 1}m")
        wait(lambda: any(call["method"] == "pane.focus" for call in calls), "single-click navigates to the explicit owner")
        focus = next(call for call in calls if call["method"] == "pane.focus")
        assert focus["params"]["pane_id"] == "foreign", focus
        wait(lambda: "Work ·" not in screen(), "owner navigation closes the board")
        send("/fixture", "Enter")
        wait(lambda: (probe / "session.json").exists(), "empty saved session created without a provider request")
        session_fixture = json.loads((probe / "session.json").read_text())
        local = session_fixture["id"]
        assert local and local != foreign and local != creator
        send("/work", "Enter")
        wait(lambda: "LIVE_WORK_FIXTURE" in screen(), "reopen board")
        send("Enter", "t")
        wait(lambda: "Message to task participants" in screen(), "task message input")
        send("Native coordination message", "Enter")
        wait(lambda: any(message["body"] == "Native coordination message" and message["session"] == local for message in store("get", id=task["id"])["messages"]), "message appends with the current session identity")
        assert task_read()["owner_session"] == foreign
        assert task_read()["notes"].startswith("## Readable notes")
        wait(lambda: screen().splitlines()[0].strip() == "Work · work", "message action settled before the next action")
        send("o")
        wait(lambda: "task is assigned to session" in screen(), "claim refuses an existing owner")
        current = task_read()
        store("release", session=foreign, id=task["id"], version=current["version"])
        current = task_read()
        store("claim", session=session_fixture["target"], id=task["id"], version=current["version"])
        wait(lambda: session_fixture["target"] in screen(), "live ownership refresh sees a different session")
        send("s")
        wait(lambda: "Work ·" not in screen(), "local owner navigation opens a saved session")
        send("/who", "Enter")
        wait(lambda: (probe / "current.json").exists(), "current pane reports its actual session")
        assert json.loads((probe / "current.json").read_text()) == session_fixture["target"], "owner navigation opened the wrong local session"
        assert task_read()["owner_session"] == session_fixture["target"], "idle native owner lost its assignment"
        current = task_read()
        store("release", session=session_fixture["target"], id=task["id"], version=current["version"])
        legacy = store("task", session=local, title="LEGACY_SOURCE_FIXTURE", status="later", notes="The creator is not the assigned session.")
        (probe / "current.json").unlink()
        send("/work", "Enter")
        wait(lambda: "LIVE_WORK_FIXTURE" in screen() and task_read()["owner_session"] == "", "unassigned task remains inspectable")
        send("l", "Enter")
        wait(lambda: "o Assign to this chat" in screen(), "unassigned task offers direct session assignment")
        assert "Open linked" not in screen() and "Open assigned" not in screen(), "creator chat is still offered as task work"
        send("s")
        wait(lambda: "not assigned to a session" in screen(), "unassigned navigation never opens the creator chat")
        send("o")
        wait(lambda: store("get", id=legacy["id"])["task"]["owner_session"] == session_fixture["target"], "task is assigned to this session")
        send("Escape", "Escape")
        wait(lambda: "Task [now]: LEGACY_SOURCE_FIXTURE" in screen(), "assigned task appears above the prompt")
        assert "Queued-input fixture row" in screen(), "task strip replaced pre-existing rows"
        current = store("get", id=legacy["id"])["task"]
        store("task", session=session_fixture["target"], id=legacy["id"], version=current["version"], title=current["title"], status="blocked", notes=current["notes"])
        wait(lambda: "Task [blocked]: LEGACY_SOURCE_FIXTURE" in screen(), "assignment status refreshes outside the work dialog")
        send("/fixture-switch source", "Enter")
        wait(lambda: "Task: not assigned" in screen() and "Task [blocked]" not in screen(), "switching to the creator does not inherit another session assignment")
        send("/fixture-switch target", "Enter")
        wait(lambda: "Task [blocked]: LEGACY_SOURCE_FIXTURE" in screen(), "switching back restores the exact session assignment")
        current = store("get", id=legacy["id"])["task"]
        store("task", session=session_fixture["target"], id=legacy["id"], version=current["version"], title=current["title"], status="done", notes=current["notes"])
        wait(lambda: "Task: not assigned" in screen() and "Task [blocked]" not in screen(), "completion clears the assignment strip")
        send("/work", "Enter")
        wait(lambda: "LIVE_WORK_FIXTURE" in screen(), "board reopens after assignment strip checks")
        send("Enter")
        wait(lambda: "TASK ACTIONS" in screen(), "inspector reopens")
        mux("resize-window", "-t", "work", "-x", "60", "-y", "24")
        wait(lambda: "TASK ACTIONS" in screen() and "Assign to this chat" in screen(), "narrow inspector retains assignment actions")
        holder_command = shlex.join(["env", "-i", *(f"{k}={v}" for k, v in env.items()), "WORK_HOLDER=1", str(binary)])
        mux("new-window", "-d", "-t", "work", "-n", "holder", "-c", str(root / "work"), holder_command)
        holder_pid = int(mux("display-message", "-p", "-t", "work:holder", "#{pane_pid}").strip())
        wait(lambda: "Project tasks" in mux("capture-pane", "-p", "-t", "work:holder"), "second native owner terminal started")
        mux("send-keys", "-t", "work:holder", "/fixture", "Enter")
        wait(lambda: (probe / "holder-session.json").exists(), "second native owner opened an idle chat")
        idle_owner = json.loads((probe / "holder-session.json").read_text())["id"]
        expiring = store("task", session=idle_owner, title="EXITED_OWNER_FIXTURE", status="now", notes="Keep this unfinished work.")
        presence = store("presence", roots={idle_owner: idle_owner})
        native_lock_support = presence["states"][idle_owner] == "open"
        assert presence["states"][idle_owner] in ("open", "unknown"), "idle native owner is incorrectly classified as closed"
        assert store("get", id=expiring["id"])["task"]["owner_session"] == idle_owner
        mux("kill-window", "-t", "work:holder")
        if native_lock_support:
            wait(lambda: store("get", id=expiring["id"])["task"]["owner_session"] == "", "closed native engine automatically releases its task while the board is open")
            expired = store("get", id=expiring["id"])
            assert expired["task"]["status"] == "now" and expired["task"]["notes"] == "Keep this unfinished work."
            assert any("assigned session is closed" in message["body"] for message in expired["messages"]), "automatic release has no audit trail"
        else:
            assert store("presence", roots={idle_owner: idle_owner})["states"][idle_owner] == "unknown"
            assert store("get", id=expiring["id"])["task"]["owner_session"] == idle_owner, "missing native lock support must preserve assignments"
            print("Native ownership locks unavailable in this binary; automatic expiry is unverified for this runtime.")
        send("Escape")
        wait(lambda: "TASK ACTIONS" not in screen(), "return from messages to board")
        send("Escape")
        wait(lambda: "Work ·" not in screen(), "work dialog closed")
        count = len(calls)
        time.sleep(3.4)
        assert len(calls) == count, "closed dialog kept polling"
        assert not any("FIXTURE_ERROR" in path.read_text(errors="replace") for path in (root / "state").rglob("*.log"))
        print(json.dumps({"done_mouse_control": True, "two_tabs": True, "github_issue_and_pr_review": True, "owner_activity": True, "idle_preserves_claim": True, "markdown": True, "right_actions": True,
                          "viewport_and_paging": True, "owner_click": True, "local_owner_navigation": True, "narrow_inspector": True, "session_attributed_message": True,
                          "claim_conflict": True, "no_creator_navigation": True, "session_task_strip": True, "strip_composition": True, "assignment_switching": True, "column_collapse": True, "temporary_preview": True, "explicit_pin": True, "thin_rails": True, "agent_identity": True, "native_idle_keeps_assignment": True, "native_closed_unassigns": native_lock_support, "close_stops_poll": True, "artifacts": str(root)}, indent=2))
    finally:
        (root / "captures.txt").write_text("\n".join(captures))
        (root / "socket-calls.json").write_text(json.dumps(calls, indent=2))
        subprocess.run(["tmux", "-L", socket, "kill-server"], capture_output=True)
        stopped = True
        for owned_pid in (pane_pid, holder_pid):
            if owned_pid is None:
                continue
            exited = False
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                try:
                    os.kill(owned_pid, 0)
                except ProcessLookupError:
                    exited = True
                    break
                time.sleep(0.05)
            stopped = stopped and exited
        server.shutdown()
        server.server_close()
        (root / "cleanup.json").write_text(json.dumps({"pane_pid": pane_pid, "holder_pid": holder_pid, "panes_exited": stopped, "socket_closed": True}))
        assert stopped, "owned native terminal process survived cleanup"
        assert (root / "captures.txt").exists() and (root / "socket-calls.json").exists()
        print("Owned terminal exited; evidence retained:", root)


if __name__ == "__main__":
    main()
