#!/usr/bin/env python3
"""Check ! commands, saved context, and masked sudo in an isolated detached terminal."""
import argparse
import http.server
import json
import os
import pathlib
import shlex
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import uuid

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--binary", default=shutil.which("yuke"))
args = parser.parse_args()
binary = pathlib.Path(args.binary).resolve()
tmux = shutil.which("tmux")
assert tmux and binary.is_file()
plugin = pathlib.Path(__file__).resolve().parents[1] / "plugins" / "sudo-command.js"
secret = "fixture-composer-password-519"
wrong = "fixture-composer-wrong-276"
requests = []
captures = []


class Provider(http.server.BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_POST(self):
        requests.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        body = 'data: {"id":"fixture","choices":[{"index":0,"delta":{"role":"assistant","content":"MODEL_REPLY_MARKER"},"finish_reason":null}]}\n\n'
        body += 'data: {"id":"fixture","choices":[{"index":0,"delta":{},"finish_reason":"stop"}],"usage":{"prompt_tokens":20,"completion_tokens":4,"total_tokens":24}}\n\n'
        body += 'data: [DONE]\n\n'
        self.wfile.write(body.encode())


server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Provider)
worker = threading.Thread(target=server.serve_forever, daemon=True)
worker.start()
try:
    with tempfile.TemporaryDirectory(prefix="yuke-composer-command-") as directory:
        root = pathlib.Path(directory)
        profile = root / "config" / "yuke"
        (profile / "plugins").mkdir(parents=True)
        env = {**os.environ, "TERM": "xterm-256color", "YUKE_APPNAME": "yuke"}
        for name in ("config", "data", "state", "cache"):
            env["XDG_" + name.upper() + "_HOME"] = str(root / name)
        for name in ("HERDR_ENV", "HERDR_SOCKET_PATH", "HERDR_PANE_ID", "AI_AGENT", "CLAUDECODE"):
            env.pop(name, None)
        (profile / "providers.json").write_text(json.dumps({"providers": [{
            "id": "fixture", "base_url": f"http://127.0.0.1:{server.server_port}/v1",
            "endpoints": [{"protocol": "openai_chat"}],
            "models": [{"id": "model", "upstream_id": "model", "flags": {"supports_tools": True}}],
        }]}))
        (profile / "providers.json").chmod(0o600)
        marker = root / "sudo-ran"
        fake = root / "sudo-fixture"
        fake.write_text("#!" + sys.executable + "\n" +
            "import os, pathlib, subprocess, sys\n"
            "assert sys.argv[1:] == ['-k', '-A', '--', '/usr/bin/id', '-u']\n"
            "assert sys.stdin.read() == ''\n"
            "for attempt in range(3):\n"
            "    response = subprocess.run([os.environ['SUDO_ASKPASS']], capture_output=True)\n"
            "    if response.returncode: sys.exit(1)\n"
            f"    if response.stdout == {secret.encode() + b'\n'!r}:\n"
            f"        pathlib.Path({str(marker)!r}).write_text('once')\n"
            "        print('SUDO_OUTPUT_MARKER')\n        sys.exit(0)\n"
            "    sys.stderr.write('Sorry, try again.\\n')\n"
            "sys.exit(1)\n")
        fake.chmod(0o700)
        (profile / "plugins" / "sudo-command.py").write_text(
            "import importlib.util, sys\n"
            f"spec = importlib.util.spec_from_file_location('helper', {str(plugin.with_suffix('.py'))!r})\n"
            "helper = importlib.util.module_from_spec(spec)\nspec.loader.exec_module(helper)\n"
            "run = helper.run\n"
            f"helper.run = lambda request, **kwargs: run(request, {str(fake)!r}, **kwargs)\n"
            "raise SystemExit(helper.main())\n")
        (profile / "index.js").write_text(
            'import { plugins } from "yuke";\n'
            'import { currentPane } from "yuke:session";\n'
            f'import {{ sudoCommand }} from {json.dumps(str(plugin))};\n'
            'plugins.use(sudoCommand);\n'
            'plugins.use({ name: "command-fixture", apply(ctx) { ctx.inject(["tui"], c => {\n'
            ' c.tui.status.add({ side: "left", render: () => "COMMAND_TEST " + (currentPane()?.session.sessionId || "draft") + " DRAFT " + (currentPane()?.composer.text || "empty") });\n'
            '}); }});\n')
        seed = {"id": "seed", "method": "session.create", "params": {"workspace_path": str(root), "model": "fixture/model"}}
        seeded = subprocess.run([str(binary), "--rpc"], cwd=root, env=env, input=json.dumps(seed) + "\n", text=True, capture_output=True, timeout=20, check=True)
        assert '"error"' not in seeded.stdout, seeded.stdout
        socket = "yuke-command-" + uuid.uuid4().hex[:10]

        def mux(*argv):
            return subprocess.check_output([tmux, "-L", socket, *argv], text=True)

        def screen(label, expected):
            deadline = time.monotonic() + 12
            while time.monotonic() < deadline:
                text = mux("capture-pane", "-p", "-t", "commands")
                assert secret not in text and wrong not in text, "password appeared on screen"
                if expected in text:
                    captures.append(f"=== {label} ===\n{text}")
                    return text
                time.sleep(0.05)
            raise AssertionError(f"missing {expected!r} at {label}\n{text}")

        def submit(text):
            mux("send-keys", "-t", "commands", "C-u")
            mux("send-keys", "-t", "commands", "-l", text)
            screen("composer input", "DRAFT " + text)
            mux("send-keys", "-t", "commands", "Enter")

        def saved_messages():
            with sqlite3.connect(root / "data" / "yuke" / "yuke.db") as db:
                return [json.loads(row[0]) for row in db.execute("SELECT payload FROM events WHERE name = 'message.committed' ORDER BY rowid")]

        try:
            command = shlex.join([str(binary)]) + "; printf '\nEXIT STATUS %s\n' \"$?\"; sleep 60"
            subprocess.run([tmux, "-L", socket, "new-session", "-d", "-x", "120", "-y", "32", "-s", "commands", "-n", "Agent Tests composer commands", "-c", str(root), command], env=env, check=True)
            screen("startup", "COMMAND_TEST draft DRAFT empty")
            submit("!pwd")
            screen("workspace output", "!pwd · exit 0")
            assert requests == [], "!pwd started a model turn"
            first = saved_messages()[-1]
            assert first["source"]["type"] == "user_shell"
            assert first["content"][1]["text"].strip() == str(root)
            submit("!printf DIRECT_OUTPUT_MARKER | cat")
            screen("pipeline output", "DIRECT_OUTPUT_MARKER")
            submit("!printf ERROR_OUTPUT_MARKER >&2; exit 7")
            screen("nonzero status", "exit 7")
            submit("!sleep 100")
            screen("running command", "Ctrl+C stops it")
            mux("send-keys", "-t", "commands", "C-c")
            screen("command cancellation", "Command canceled. It may have started.")
            submit("!sudo id -u")
            screen("sudo approval", "Run as root?")
            mux("send-keys", "-t", "commands", "Escape")
            screen("sudo declined", "Sudo request declined or canceled. No command ran.")
            assert not marker.exists()
            submit("!sudo id -u")
            screen("sudo approval accepted", "Run as root?")
            mux("send-keys", "-t", "commands", "Enter")
            screen("masked password", "Sudo password (local only)")
            mux("send-keys", "-t", "commands", "-l", wrong)
            mux("send-keys", "-t", "commands", "Enter")
            screen("masked retry", "attempt 2")
            mux("send-keys", "-t", "commands", "-l", secret)
            mux("send-keys", "-t", "commands", "Enter")
            screen("sudo command output", "SUDO_OUTPUT_MARKER")
            assert marker.read_text() == "once"
            assert requests == [], "a direct command started a model turn"
            submit("Now read the command output.")
            screen("normal model reply", "MODEL_REPLY_MARKER")
            assert len(requests) == 1, "one normal submission must make one model request"
            context = json.dumps(requests[0])
            for text in ("DIRECT_OUTPUT_MARKER", "ERROR_OUTPUT_MARKER", "SUDO_OUTPUT_MARKER"):
                assert text in context, "the next model turn did not receive " + text
            assert secret not in context and wrong not in context
            for message in saved_messages():
                serialized = json.dumps(message)
                assert secret not in serialized and wrong not in serialized
            for path in (root / "state").rglob("*"):
                if path.is_file():
                    assert secret.encode() not in path.read_bytes() and wrong.encode() not in path.read_bytes()
            mux("send-keys", "-t", "commands", "C-q")
            screen("clean exit", "EXIT STATUS 0")
        finally:
            subprocess.run([tmux, "-L", socket, "kill-server"], capture_output=True, check=False)
finally:
    server.shutdown()
    server.server_close()
    worker.join(timeout=5)
    with tempfile.NamedTemporaryFile(prefix="yuke-composer-command-captures-", suffix=".txt", mode="w", delete=False) as artifact:
        artifact.write("\n".join(captures))
        print("Saved composer command captures:", artifact.name)

print("Direct shell, pipeline, error, cancellation, sudo retry, saved context, and password privacy checks passed")
