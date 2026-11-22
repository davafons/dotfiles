#!/usr/bin/env python3
"""Check the Rust personal profile in a private terminal without credentials or model calls."""
import fcntl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import json
import importlib.util
import subprocess
import os
from pathlib import Path
import pty
import re
import select
import shutil
import signal
import struct
import tempfile
import termios
import time

profile = Path(__file__).resolve().parents[1] / ".config/yuke-rust"
binary = shutil.which(os.environ.get("YUKE_BINARY", "yuke"))
if binary is None:
    raise SystemExit("Set YUKE_BINARY to the Yuke executable")
width, height = 80, 24
transcript = bytearray()
control = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07\x1b]*(?:\x07|\x1b\\))")

with tempfile.TemporaryDirectory(prefix="yuke-vim-terminal-") as directory:
    root = Path(directory)
    config = root / "config/yuke"
    config.mkdir(parents=True)
    shutil.copytree(profile, config, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    (root / "work").mkdir()
    (root / "work/folder").mkdir()
    (root / "work/folder/nested.txt").write_text("fixture\n")
    (root / "work/cd folder").mkdir()
    requests = []
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            requests.append(self.path)
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b'{"error":{"message":"No model request is allowed in this check."}}')
        def log_message(self, *_args):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    (config / "providers.json").write_text(json.dumps({"providers": [{"id": "fixture", "baseUrl": f"http://127.0.0.1:{server.server_port}/v1", "endpoints": [{"protocol": "openai_chat"}], "models": [{"id": "fixture", "reasoningLevels": ["medium"], "limits": {"contextWindow": 10000, "maxOutputTokens": 1000}}]}]}))
    fake_sudo = root / "sudo-fixture"
    fake_sudo.write_text("#!/usr/bin/env python3\n" + "import os, subprocess, sys\n" + "assert sys.argv[1:4] == ['-k', '-A', '--']\n" + "secret = subprocess.check_output([os.environ['SUDO_ASKPASS'], 'Password:']).decode().strip()\n" + "print('sudo-fixture-output ' + secret)\n" + "print('sudo-fixture-stderr ' + secret, file=sys.stderr)\n")
    fake_sudo.chmod(0o700)
    sudo_helper = config / "helpers/sudo-command.py"
    sudo_helper.write_text(sudo_helper.read_text().replace("result = run(request, password_buffer=incoming)", f"result = run(request, sudo={str(fake_sudo)!r}, password_buffer=incoming)"))
    ready = root / "mounted.txt"
    notices = root / "notices.jsonl"
    probe = root / "probe"
    probe.mkdir()
    (probe / "plugin.json").write_text(json.dumps({"name": "vim-probe", "extensions": {"sh.yuke": {"entry": "index.ts"}}}))
    (probe / "index.ts").write_text('''import { writeTextFile } from "yuke:fs";
export function apply(ctx) {
  const tui = ctx.get("tui");
  if (tui === undefined) return;
  const record = (notice) => { if (notice.level === "error") void writeTextFile(NOTICES, JSON.stringify(notice) + "\\n", { append: true }); };
  tui.notices.list().forEach(record);
  tui.notices.addListener(record);
  let recorded = false;
  tui.widgets.addWatcher((mount) => {
    if (mount.widget.kind === "editor" && mount.widget.role !== "composer") void writeTextFile(READY, "dialog-editor\\n", { append: true });
    if (recorded || mount.widget.kind !== "editor" || mount.widget.role !== "composer") return;
    recorded = true;
    void writeTextFile(READY, "mounted\\n", { append: true }).catch((error) => ctx.notify("error", String(error)));
  });
}
'''.replace("READY", json.dumps(str(ready))).replace("NOTICES", json.dumps(str(notices))))
    plugins = []
    for item in json.loads((profile / "config.json").read_text())["plugins"]:
        if isinstance(item, dict) and "git" in item:
            plugins.append(item)
            continue
        path = item["path"] if isinstance(item, dict) else item
        if path == "./plugins/models":
            plugins.append({"path": str(config / path), "options": {"startupModel": "fixture/fixture", "startupEffort": "medium"}})
        elif isinstance(item, dict):
            plugins.append(dict(item, path=str(config / path)))
        else:
            plugins.append(str(config / path))
    (config / "config.json").write_text(json.dumps({"plugins": plugins + [str(probe)]}))
    environment = dict(
        PATH=os.environ["PATH"], HOME=str(root), YUKE_APPNAME="yuke", XDG_CONFIG_HOME=str(root / "config"),
        XDG_DATA_HOME=str(root / "data"), XDG_CACHE_HOME=str(root / "cache"),
        YUKE_EXECUTABLE=binary, TERM="xterm-256color", COLORTERM="truecolor",
    )
    # Git plugins install into the private data folder at their plugins.lock commits.
    subprocess.run([binary, "plugin", "sync", "--locked"], env=environment, check=True, capture_output=True)
    spec = importlib.util.spec_from_file_location('inbox', config / 'helpers/yuke-clarify-store.py')
    inbox = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(inbox)
    inbox_path = root / 'data/yuke/plugins/yuke-clarify/questions.sqlite3'
    question = inbox.operate(str(inbox_path), 'add', dict(session='1' * 32, site='legacy-fixture', question=dict(title='Retained inbox fixture', question='Keep these notes?', context='', options=[], multi_select=False)))
    process, terminal = pty.fork()
    if process == 0:
        os.chdir(root / "work")
        os.execve(binary, [binary], environment)
    fcntl.ioctl(terminal, termios.TIOCSWINSZ, struct.pack("HHHH", height, width, 0, 0))

    def pump():
        ready, _, _ = select.select([terminal], [], [], 0.05)
        if ready:
            try:
                data = os.read(terminal, 65536)
            except OSError:
                return
            transcript.extend(data)
            if b"\x1b]11;?" in data:
                os.write(terminal, b"\x1b]11;rgb:1111/1111/1111\x1b\\\x1b[?0u\x1b[?62c")

    def screen():
        cells = [[" "] * width for _ in range(height)]
        row = column = offset = 0
        text = transcript.decode(errors="replace")
        while offset < len(text):
            character = text[offset]
            if character == "\x1b":
                match = control.match(text, offset)
                if match is None:
                    break
                sequence = match.group()
                if sequence.startswith("\x1b["):
                    if sequence.endswith("H"):
                        coordinates = sequence[2:-1].split(";")
                        row = int(coordinates[0] or "1") - 1
                        column = int(coordinates[1] or "1") - 1 if len(coordinates) > 1 else 0
                    elif sequence.endswith("J") and sequence[2:-1] in ("", "2", "3"):
                        cells = [[" "] * width for _ in range(height)]
                offset = match.end()
                continue
            if character == "\r":
                column = 0
            elif character == "\n":
                row += 1
            elif character >= " ":
                if 0 <= row < height and 0 <= column < width:
                    cells[row][column] = character
                column += 1
            offset += 1
        return ["".join(line).rstrip() for line in cells]

    def wait_for(predicate):
        deadline = time.monotonic() + 10
        while not predicate(screen()):
            if time.monotonic() >= deadline:
                raise AssertionError("\n".join(screen()))
            pump()

    def contains(value):
        return lambda rows: any(value in row for row in rows)

    try:
        wait_for(contains("NORMAL"))
        wait_for(contains("unleash your harness"))
        # The dashboard belongs to the empty transcript area, below notices and dialogs.
        height = 36
        fcntl.ioctl(terminal, termios.TIOCSWINSZ, struct.pack("HHHH", height, width, 0, 0))
        os.kill(process, signal.SIGWINCH)
        def dashboard_complete(rows):
            top = next((index for index, row in enumerate(rows) if "██╗   ██╗" in row), -1)
            return top >= 0 and top + 18 < len(rows) and "Sign in" in rows[top + 10] and "Commands" in rows[top + 15] and "unleash your harness" in rows[top + 18]
        wait_for(dashboard_complete)
        wait_for(contains("fixture medium"))
        rows = screen()
        commands_row = next(index for index, row in enumerate(rows) if "Commands" in row)
        menu_column = rows[commands_row].index("Commands")
        assert menu_column > 0 and rows[commands_row].rstrip().endswith("c")
        preview = Path(os.environ.get("YUKE_DASHBOARD_FRAME", "/tmp/yuke-dashboard-frame.json"))
        preview.write_text(json.dumps(dict(width=width, height=height, rows=rows)))
        os.write(terminal, f"\x1b[<0;{menu_column + 2};{commands_row + 1}M\x1b[<0;{menu_column + 2};{commands_row + 1}m".encode())
        wait_for(lambda rows: any("Commands" in row and "esc: close" not in row for row in rows) and any("core:" in row or "dashboard:" in row for row in rows))
        os.write(terminal, b"\x1b")
        wait_for(contains("unleash your harness"))
        height = 24
        fcntl.ioctl(terminal, termios.TIOCSWINSZ, struct.pack("HHHH", height, width, 0, 0))
        os.kill(process, signal.SIGWINCH)
        wait_for(lambda rows: contains("YUKE")(rows) and not contains("██╗   ██╗")(rows))
        os.write(terminal, b"ialpha beta gamma")
        wait_for(contains("alpha beta gamma"))
        assert not contains("unleash your harness")(screen())
        os.write(terminal, b"\x1b")
        wait_for(contains("NORMAL"))
        os.write(terminal, b"0dw")
        wait_for(lambda rows: any(row.strip() == "beta gamma" for row in rows))
        os.write(terminal, b"u")
        wait_for(contains("alpha beta gamma"))
        os.write(terminal, b"0ciwHELLO\x1b")
        wait_for(contains("HELLO beta gamma"))
        wait_for(contains("NORMAL"))
        os.write(terminal, b"\x03")
        wait_for(contains("Message"))
        os.write(terminal, b"i./folder/n")
        wait_for(contains("nested.txt"))
        os.write(terminal, b"\t")
        wait_for(contains("./folder/nested.txt"))
        os.write(terminal, b"\x03i/cd cd")
        wait_for(contains("cd folder/"))
        os.write(terminal, b"\t")
        wait_for(contains('/cd "./cd folder/"'))
        os.write(terminal, b"\x03i/panel vsplit\r")
        wait_for(contains("│"))
        os.write(terminal, b"/panel only\r")
        wait_for(lambda rows: not any("│" in row for row in rows))
        # Personal commands and the btw Git plugin show as slash completions.
        os.write(terminal, b"/pan")
        wait_for(contains("<split|vsplit|close|only>"))
        os.write(terminal, b"\x03i/bt")
        wait_for(contains("btw:history"))
        os.write(terminal, b"\x03i/clear\r")
        wait_for(contains("Message"))
        wait_for(lambda rows: ready.exists())
        mounts = ready.read_text().count("mounted\n")
        os.write(terminal, b"/reload\r")
        # A public widget mount callback acknowledges the new runtime.
        wait_for(lambda rows: ready.read_text().count("mounted\n") > mounts and contains("NORMAL")(rows) and contains("Message")(rows))
        os.write(terminal, b"iafter reload")
        wait_for(contains("after reload"))
        os.write(terminal, b"\x1b")
        wait_for(contains("NORMAL"))
        os.write(terminal, b"0dw")
        wait_for(lambda rows: any(row.strip() == "reload" for row in rows))
        os.write(terminal, b"\x03i!printf 'direct-record-fixture\\n'\r")
        wait_for(contains("direct-record-fixture"))
        wait_for(contains("Exit 0"))
        os.write(terminal, b"\x1b")
        wait_for(lambda rows: not any("Direct command" in row for row in rows))
        os.write(terminal, b"!sudo /bin/echo sudo-fixture\r")
        wait_for(contains("Do not run"))
        os.write(terminal, b"\x1b[B\r")
        wait_for(contains("Sudo password"))
        os.write(terminal, b"migration-only-secret\r")
        wait_for(contains("sudo-fixture-output"))
        wait_for(contains("[REDACTED]"))
        wait_for(contains("Exit 0"))
        assert b"migration-only-secret" not in transcript
        os.write(terminal, b"\x1b")
        wait_for(lambda rows: not any("Direct command" in row for row in rows))
        os.write(terminal, b"/context\r")
        wait_for(contains("Context budget"))
        os.write(terminal, b"\t")
        wait_for(contains("Saved context"))
        os.write(terminal, b"\t")
        wait_for(contains("Prompt preview"))
        os.write(terminal, b"\t")
        wait_for(contains("Registered tools"))
        os.write(terminal, b"\x1b")
        wait_for(lambda rows: not contains("Context ·")(rows))
        os.write(terminal, b"/usage\r")
        wait_for(contains("Overview"))
        wait_for(contains("0 responses"))
        os.write(terminal, b"\x1b")
        wait_for(lambda rows: not contains("Usage ·")(rows))
        os.write(terminal, b"/work\r")
        wait_for(contains("Project work"))
        os.write(terminal, b"\x1bn")
        wait_for(contains("New task"))
        os.write(terminal, b"Terminal task fixture\x13")
        wait_for(lambda rows: not any("New task" in row for row in rows))
        wait_for(contains("Terminal task fixture"))
        os.write(terminal, b"\x1b")
        wait_for(lambda rows: not contains("Project work ·")(rows))
        os.write(terminal, b"/search nested\r")
        wait_for(contains("nested.txt"))
        os.write(terminal, b"\x1b")
        saved = "".join(log.read_text() for log in (root / "data/yuke/sessions").glob("*/events.jsonl"))
        assert "migration-only-secret" not in saved
        assert "[REDACTED]" in saved
        # Preserve an old pending question without sending it or answering it.
        wait_for(lambda rows: not contains("Search ·")(rows))
        os.write(terminal, b"/questions\r")
        wait_for(contains("Question inbox"))
        os.write(terminal, b"\r")
        wait_for(contains("Keep these notes?"))
        os.write(terminal, b"retained draft fixture")
        wait_for(contains("retained draft fixture"))
        os.write(terminal, b"\x1b")
        wait_for(lambda rows: not contains("Keep these notes?")(rows))
        wait_for(lambda rows: inbox.operate(str(inbox_path), 'list', {})[0]['draft']['text'] == 'retained draft fixture')
        os.write(terminal, b"/questions\r")
        wait_for(contains("Question inbox"))
        os.write(terminal, b"\r")
        wait_for(contains("retained draft fixture"))
        dialog_mounts = ready.read_text().count("dialog-editor\n")
        os.write(terminal, b"\x0f")
        wait_for(contains("Move these pending questions"))
        os.write(terminal, b"\r")
        wait_for(lambda rows: ready.read_text().count("dialog-editor\n") > dialog_mounts)
        wait_for(contains("Keep these notes?"))
        moved = inbox.operate(str(inbox_path), 'list', {})[0]
        assert moved['session'] != '1' * 32 and moved['origin_session'] == '1' * 32
        assert moved['draft']['text'] == 'retained draft fixture' and moved['status'] == 'pending'
        os.write(terminal, b"\x1b")
        wait_for(lambda rows: not contains("Keep these notes?")(rows))
        os.write(terminal, b'/clear\r')
        wait_for(contains("Message"))
        os.write(terminal, b'/cd "./cd folder"\r')
        wait_for(contains("Workspace:"))
        os.write(terminal, b'!pwd\r')
        wait_for(lambda rows: contains("Direct command")(rows) and contains("Exit 0")(rows))
        folders = {}
        for line in (root / 'data/yuke/sessions.jsonl').read_text().splitlines():
            row = json.loads(line)
            if row.get('meta') is not None:
                folders[row['id']] = row['meta']['folder']
        assert list(folders.values()).count(str((root / 'work/cd folder').resolve())) == 1
        assert requests == [], f"Unexpected model requests: {requests}"
        assert not notices.exists() or notices.read_text() == "", notices.read_text() if notices.exists() else ""
        print("PASS real terminal: profile, dashboard, Vim, paths, panes, reload, recorded commands, masked sudo, context, usage, tasks, search, retained inbox adoption, workspace switch, slash completions, btw Git plugin; zero model requests")
    finally:
        Path(os.environ.get("YUKE_VIM_TERMINAL_LOG", "/tmp/yuke-vim-terminal.log")).write_bytes(transcript)
        os.kill(process, signal.SIGTERM)
        deadline = time.monotonic() + 5
        while os.waitpid(process, os.WNOHANG) == (0, 0):
            if time.monotonic() >= deadline:
                os.kill(process, signal.SIGKILL)
                os.waitpid(process, 0)
                raise AssertionError("Yuke did not stop within five seconds of SIGTERM")
            pump()
        os.close(terminal)
        server.shutdown()
        server.server_close()
