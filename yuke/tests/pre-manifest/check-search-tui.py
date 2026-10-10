#!/usr/bin/env python3
"""Drive native search, paged history, draft insertion, cache reuse, and Herdr in detached tmux."""
import fcntl
import json
from pathlib import Path
import shlex
import sqlite3
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import uuid

TMUX, YUKE = shutil.which("tmux"), shutil.which("yuke")
assert TMUX and YUKE, "tmux and yuke are required"
PLUGIN = Path(__file__).resolve().parents[1] / "plugins/search.js"
HELPER = PLUGIN.with_name("search-store.py")
NAME = "yuke-search-" + uuid.uuid4().hex[:10]
captures = []
focus_requests = []
server_errors = []
stopped = threading.Event()
reported_pane = "wTest:p1"
reject_focus = False


def tmux(*args, check=True):
    return subprocess.run([TMUX, "-L", NAME, *args], check=check, text=True, capture_output=True)


def wait_screen(label, predicate, timeout=15):
    deadline = time.monotonic() + timeout
    screen = ""
    while time.monotonic() < deadline:
        screen = tmux("capture-pane", "-t", "test", "-p").stdout
        if predicate(screen):
            captures.append(f"=== {label} ===\n{screen}")
            return screen
        time.sleep(0.05)
    raise AssertionError(f"timed out: {label}\n{screen}\n{server_errors}")


def worker_count():
    pid = int(tmux("display-message", "-p", "-t", "test", "#{pane_pid}").stdout)
    rows = subprocess.check_output(["ps", "-axo", "pid,ppid,command"], text=True).splitlines()[1:]
    return sum(int(row.split(None, 2)[1]) == pid and "search-store.py" in row for row in rows if len(row.split(None, 2)) == 3)


def wait_workers(count):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if worker_count() == count:
            return
        time.sleep(0.05)
    raise AssertionError(f"expected {count} search workers, got {worker_count()}")


def query(value):
    tmux("send-keys", "-t", "test", "C-a")
    tmux("send-keys", "-t", "test", "-N", "100", "Delete")
    if value:
        tmux("send-keys", "-t", "test", "-l", value)


PROFILE = r'''
import { client, plugins } from "yuke";
import { currentPane } from "yuke:session";
import { search } from PLUGIN;
import { solarizedTheme } from THEME;
const now = Date.now();
let reads = 0, opened = "none", broken = false;
const activity = {state: {type: "idle"}, queued: 0, context_tokens: 0, pending_compaction: null};
const item = (id, title, root) => ({session: {
  id, title, root, model: "test/model", reasoning: "", config_rev: 1, max_rounds: 20,
  usage_total: {input: 0, output: 0, reasoning: 0, cache_read: 0, cache_write: 0},
  cost: {total: 0, without_cache: 0, unpriced: 0}, created_at_ms: now, updated_at_ms: now,
  message_count: 2, origin: {type: "root"},
}, activity});
const local = item("local", "Ownership review", WORKSPACE);
const other = item("other", "Cross workspace design", "/other-workspace");
const foreign = item("foreign", "Foreign owner", WORKSPACE);
const items = [local, other, foreign];
client.sessionList = async (params = {}) => params.cursor
  ? {revision: 1, items: items.slice(1), total: 3}
  : {revision: 1, items: items.slice(0, 1), next_cursor: "second", total: 3};
let changed = false;
client.sessionGet = async (id) => {
  if (id === "local" && !changed) {
    changed = true;
    const latest = {...local, session: {...local.session, updated_at_ms: now + 1, message_count: 3}};
    items[0] = latest;
    histories.local.push(assistant(3, "A newly committed sapphire answer."));
  }
  return items.find(item => item.session.id === id);
};
const user = (id, value) => ({type: "user", id, input_id: id, time: {created_at_ms: now}, content: [{type: "text", text: value}]});
const assistant = (id, value) => ({type: "assistant", id, run_id: 1, config_rev: 1, time: {created_at_ms: now, completed_at_ms: now}, finish: "stop", content: [{type: "text", id: 0, text: value}]});
const histories = {
  local: [user(1, "Ancient quartz appears only in the older page."), assistant(2, Array.from({length: 80}, (_, i) => "Ownership detail " + (i + 1)).join("\n\n"))],
  other: [user(1, "Cobalt is in another workspace."), assistant(2, "Other answer")],
  foreign: [user(1, "Foreign zircon is useful."), assistant(2, "Foreign answer")],
};
histories.local[1].content.push({type: "text", id: 1, text: "x".repeat(31999) + "🐈 boundary"});
client.request = async (method, params) => {
  if (method !== "session.history") throw new Error("unexpected " + method);
  reads++;
  if (broken && params.session_id === "local") throw new Error("fixture history failure");
  const messages = histories[params.session_id];
  if (params.session_id === "local" && params.before_message_id === 0) return {session_id: "local", messages: messages.slice(1), configs: [], has_more: true};
  return {session_id: params.session_id, messages: params.session_id === "local" ? messages.slice(0, 1) : messages, configs: [], has_more: false};
};
client.sessionOpen = (id) => {
  if (id === "foreign") throw new Error("must not open foreign locally");
  opened = id; return true;
};
client.sessionClose = () => {};
client.sessionActivity = () => activity;
client.sessionOutline = () => ({messages: [], active: null});
client.sessionCheckContext = async () => local;
plugins.use(solarizedTheme);
plugins.use(search);
plugins.use({name: "search-test", apply(ctx) { ctx.inject(["tui"], c => {
  c.tui.status.add({side: "left", render: () => "SEARCH TEST READY reads=" + reads + " opened=" + opened});
  c.tui.keymap.add({"ctrl+g": "search:open"}, "chat && !overlay");
  c.tui.command.add("dispose", {aboveModal: true, run: () => plugins.dispose("search")});
  c.tui.keymap.add({"ctrl+x": "search-test:dispose"});
  c.tui.command.add("fail-history", {aboveModal: true, run: () => {
    broken = true;
    items[0] = {...items[0], session: {...items[0].session, updated_at_ms: now + 2, message_count: 4}};
  }});
  c.tui.keymap.add({"ctrl+b": "search-test:fail-history"});
}); }});
'''


def serve(server):
    while not stopped.is_set():
        try:
            connection, _ = server.accept()
        except socket.timeout:
            continue
        try:
            with connection:
                data = b""
                while not data.endswith(b"\n"):
                    chunk = connection.recv(4096)
                    if not chunk:
                        break
                    data += chunk
                if not data:
                    continue
                request = json.loads(data)
                response = {"id": request["id"]}
                if request["method"] == "pane.list":
                    response["result"] = {"type": "pane_list", "panes": [{"pane_id": reported_pane, "agent": "yuke", "tokens": {"yuke_session_id": "foreign"}}]}
                elif request["method"] == "pane.focus":
                    focus_requests.append(request["params"]["pane_id"])
                    if reject_focus:
                        response["error"] = {"message": "test owner vanished"}
                    else:
                        response["result"] = {"type": "ok"}
                else:
                    raise AssertionError(request)
                connection.sendall((json.dumps(response) + "\n").encode())
        except Exception as error:
            server_errors.append(repr(error))


try:
    with tempfile.TemporaryDirectory(prefix="yuke-search-tui-") as directory:
        root = Path(directory).resolve()
        workspace = root / "workspace"
        workspace.mkdir()
        (workspace / "visible space.txt").write_text("File nebula appears here.\n")
        (workspace / ".ignore").write_text("ignored.txt\n")
        (workspace / "ignored.txt").write_text("File nebula secret\n")
        config = root / "config/yuke"
        (config / "plugins").mkdir(parents=True)
        (config / "plugins/search-store.py").symlink_to(HELPER)
        (config / "index.js").write_text(PROFILE.replace("PLUGIN", json.dumps(str(PLUGIN))).replace("WORKSPACE", json.dumps(str(workspace))).replace("THEME", json.dumps(str(PLUGIN.with_name("solarized-theme.js")))))
        owners = root / "data/yuke/yuke.db.owners"
        owners.mkdir(parents=True)
        lock = (owners / "foreign.lock").open("a+b")
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        socket_path = root / "herdr.sock"
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(str(socket_path))
        server.listen()
        server.settimeout(0.05)
        thread = threading.Thread(target=serve, args=(server,), daemon=True)
        thread.start()
        run = root / "run.sh"
        variables = {"XDG_CONFIG_HOME": root / "config", "XDG_DATA_HOME": root / "data", "XDG_STATE_HOME": root / "state", "XDG_CACHE_HOME": root / "cache", "HERDR_ENV": "1", "HERDR_SOCKET_PATH": socket_path, "TERM": "xterm-256color", "COLORTERM": ""}
        run.write_text("#!/bin/sh\n" + "".join("export " + key + "=" + shlex.quote(str(value)) + "\n" for key, value in variables.items()) + "cd " + shlex.quote(str(workspace)) + "\nexec " + shlex.quote(YUKE) + "\n")
        run.chmod(0o700)
        tmux("new-session", "-d", "-x", "160", "-y", "42", "-s", "test", str(run))
        wait_screen("ready", lambda screen: "SEARCH TEST READY" in screen)
        wait_workers(0)
        tmux("send-keys", "-t", "test", "-l", "Keep my draft")
        tmux("send-keys", "-t", "test", "C-g")
        wait_screen("native finder", lambda screen: "Search · workspace · all" in screen and "Saved chat index ready" in screen and "reads=6" in screen)
        wait_workers(1)
        with sqlite3.connect(root / "cache/yuke/search/history-v1.db") as database:
            body = database.execute("SELECT body FROM passages WHERE session_id='local' AND part_id=1").fetchone()[0]
            assert body == "x" * 31999 + "🐈 boundary", "history chunks broke a surrogate pair"
        query("sapphire")
        wait_screen("changed history retries", lambda screen: "CHAT  Ownership review" in screen and "newly committed sapphire" in screen)
        query("ancient quartz")
        wait_screen("older history search", lambda screen: "CHAT  Ownership review" in screen and "older page" in screen)
        ansi = tmux("capture-pane", "-t", "test", "-p", "-e").stdout
        chat_row = next(row for row in ansi.splitlines() if "CHAT" in row and "Ownership review" in row)
        match_row = next(row for row in ansi.splitlines() if "Ancient" in row and "older page" in row and "[Ancient]" not in row)
        assert "38;5;80" in chat_row, "chat badge is not theme cyan"
        assert "38;5;179" in match_row, "preview match is not theme yellow"
        tmux("send-keys", "-t", "test", "C-y")
        screen = wait_screen("quote insertion", lambda screen: "Search ·" not in screen and "Ancient quartz" in screen)
        assert "Keep my draft" in screen and "opened=none" in screen, screen
        wait_workers(0)
        tmux("send-keys", "-t", "test", "C-g")
        wait_screen("index cache reused", lambda screen: "Saved chat index ready" in screen and "reads=6" in screen)
        query("cobalt")
        wait_screen("workspace excludes other chat", lambda screen: "No matches" in screen)
        tmux("send-keys", "-t", "test", "Tab")
        wait_screen("all session scope", lambda screen: "CHAT  Cross workspace design" in screen and "another workspace" in screen)
        tmux("send-keys", "-t", "test", "Tab")
        query("Ownership detail")
        wait_screen("long passage preview", lambda screen: "Ownership detail 1" in screen)
        tmux("send-keys", "-t", "test", "C-d")
        wait_screen("preview scroll", lambda screen: "Ownership detail 20" in screen or "Ownership detail 30" in screen)
        query("nebula")
        screen = wait_screen("file content search", lambda screen: "TEXT  visible space.txt:1" in screen and "File nebula appears here" in screen)
        assert "ignored.txt" not in screen, screen
        ansi = tmux("capture-pane", "-t", "test", "-p", "-e").stdout
        file_row = next(row for row in ansi.splitlines() if "TEXT" in row and "visible space.txt" in row)
        assert "38;5;113" in file_row, "file badge is not theme green"
        tmux("send-keys", "-t", "test", "Enter")
        screen = wait_screen("path insertion", lambda screen: "Search ·" not in screen and "visible space.txt" in screen)
        assert "Keep my draft" in screen and "Ancient quartz" in screen and "opened=none" in screen, screen
        tmux("send-keys", "-t", "test", "C-g")
        wait_screen("third open", lambda screen: "Saved chat index ready" in screen)
        query("vis")
        wait_screen("fuzzy path", lambda screen: "FILE  visible space.txt" in screen)
        tmux("send-keys", "-t", "test", "C-t")
        wait_screen("source cycle", lambda screen: "Search · workspace · chats" in screen and "No matches" in screen)
        query("Foreign owner")
        wait_screen("foreign navigation label", lambda screen: "SESSION  Foreign owner" in screen and "jump to Herdr" in screen)
        reject_focus = True
        tmux("send-keys", "-t", "test", "Enter")
        wait_screen("foreign failure preserves finder", lambda screen: "test owner vanished" in screen and "Search ·" in screen)
        reject_focus = False
        reported_pane = "wMoved:p2"
        tmux("send-keys", "-t", "test", "Enter")
        wait_screen("foreign jump closes finder", lambda screen: "Search ·" not in screen and "opened=none" in screen)
        assert focus_requests == ["wTest:p1", "wMoved:p2"], focus_requests
        tmux("send-keys", "-t", "test", "C-g")
        wait_screen("fourth open", lambda screen: "Saved chat index ready" in screen)
        query("Ownership review")
        wait_screen("local session result", lambda screen: "SESSION  Ownership review" in screen)
        tmux("send-keys", "-t", "test", "Enter")
        wait_screen("local session opens", lambda screen: "Search ·" not in screen and "opened=local" in screen)
        tmux("send-keys", "-t", "test", "C-g")
        wait_screen("cancel finder", lambda screen: "Search ·" in screen)
        tmux("send-keys", "-t", "test", "Escape")
        wait_screen("cancel preserves process", lambda screen: "Search ·" not in screen and "SEARCH TEST READY" in screen)
        wait_workers(0)
        tmux("send-keys", "-t", "test", "C-g")
        wait_screen("unload active finder", lambda screen: "Saved chat index ready" in screen)
        wait_workers(1)
        tmux("send-keys", "-t", "test", "C-b", "C-r")
        wait_screen("real indexing error gives its cause", lambda screen: "1 failed: fixture history failure" in screen)
        ansi = tmux("capture-pane", "-t", "test", "-p", "-e").stdout
        error_row = next(row for row in ansi.splitlines() if "fixture history failure" in row)
        assert "38;5;209" in error_row, "index error is not theme red"
        query("sapphire")
        wait_screen("failed replacement excludes stale text", lambda screen: "No matches" in screen and "fixture history failure" in screen)
        tmux("send-keys", "-t", "test", "C-x")
        wait_screen("unload removes finder", lambda screen: "Search ·" not in screen and "SEARCH TEST READY" in screen)
        wait_workers(0)
        assert not server_errors, server_errors
        state_log = root / "state/yuke/yuke.log"
        if state_log.exists():
            log = state_log.read_text()
            assert "fixture history failure" in log and "script fault" not in log, log
        stopped.set()
        thread.join(timeout=2)
        server.close()
        lock.close()
finally:
    stopped.set()
    tmux("kill-server", check=False)
    with tempfile.NamedTemporaryFile(prefix="yuke-search-tui-", suffix=".txt", mode="w", delete=False) as artifact:
        artifact.write("\n".join(captures))
        print("Saved search transcript:", artifact.name)

print("Native search tmux check passed")
