#!/usr/bin/env python3
"""Verify model controls with real TUI keys and a loopback provider."""
import http.server
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import threading
import time
import uuid

TMUX = shutil.which("tmux")
YUKE = os.environ.get("YUKE_TEST_BINARY") or shutil.which("yuke")
assert TMUX and YUKE, "tmux and yuke are required"
PROFILE = Path(__file__).resolve().parents[1]
SOCKET = "yuke-model-manager-" + uuid.uuid4().hex[:10]
CAPTURES = []
REQUESTS = []
ERRORS = []
PROBE = 0


def tmux(*args, check=True):
    return subprocess.run([TMUX, "-L", SOCKET, *args], check=check, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def expect(label, *words, absent=()):
    deadline = time.monotonic() + 10
    screen = ""
    while time.monotonic() < deadline:
        screen = tmux("capture-pane", "-t", "test", "-p").stdout
        if all(word in screen for word in words) and all(word not in screen for word in absent):
            CAPTURES.append(f"=== {label} ===\n{screen}")
            return screen
        time.sleep(0.05)
    CAPTURES.append(f"=== FAILED {label} ===\n{screen}")
    raise AssertionError(f"{label}: expected {words}, absent {absent}\n{screen}\n{ERRORS}")


def keys(*values):
    tmux("send-keys", "-t", "test", *values)


def literal(value):
    tmux("send-keys", "-t", "test", "-l", value)


def command(value):
    literal(value)
    keys("Enter")


def persisted(label, model, effort):
    global PROBE
    deadline = time.monotonic() + 10
    selected = model + (" · " + effort if effort else "")
    while time.monotonic() < deadline:
        status = tmux("capture-pane", "-t", "test", "-p").stdout.splitlines()[-1]
        if selected in status:
            break
        time.sleep(0.05)
    else:
        raise AssertionError(f"{label}: status did not show {selected}: {status}")
    PROBE += 1
    keys("F8")
    expect(label, f"P{PROBE} {model} [{effort}]")


class Provider(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        try:
            assert self.path == "/v1/chat/completions", self.path
            REQUESTS.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            for delta, finish in (({"content": "Model manager test reply."}, None), ({}, "stop")):
                event = {"id": "model-test", "choices": [{"index": 0, "delta": delta, "finish_reason": finish}]}
                self.wfile.write(("data: " + json.dumps(event) + "\n\n").encode())
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        except Exception as error:
            ERRORS.append(repr(error))
            self.send_error(500)


server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Provider)
threading.Thread(target=server.serve_forever, daemon=True).start()
try:
    with tempfile.TemporaryDirectory(prefix="yuke-model-manager-") as directory:
        root = Path(directory).resolve()
        profile = root / "config/yuke"
        profile.mkdir(parents=True)
        (profile / "plugins").mkdir()
        (profile / "plugins/model-alias-store.py").symlink_to(PROFILE / "plugins/model-alias-store.py")
        (root / "workspace").mkdir()
        (profile / "index.js").write_text(
            'import { plugins, client } from "yuke";\n'
            'import { currentPane } from "yuke:session";\n'
            f'import {{ modelManager }} from {json.dumps(str(PROFILE / "plugins/model-manager.js"))};\n'
            f'import {{ effortStatus }} from {json.dumps(str(PROFILE / "plugins/effort-status.js"))};\n'
            'plugins.use(effortStatus);\n'
            'const manager = () => modelManager({ modelKey: "ctrl+x m", effortKey: "ctrl+x e", presets: [\n'
            '  { alias: "mh", model: "manager-test/middle", effort: "high", key: "ctrl+x h" },\n'
            '  { alias: "missing", model: "manager-test/missing" },\n'
            '  { alias: "bad", model: "manager-test/alpha", effort: "high" },\n'
            '  { alias: "sh", latest: { provider: "manager-test", family: "sol" }, effort: "high", key: "ctrl+x s" },\n'
            '  { alias: "lm", latest: { provider: "manager-test", family: "luna" }, effort: "medium", key: "ctrl+x l" },\n'
            ']});\n'
            'plugins.use(manager());\n'
            'plugins.use({ name: "model-test-probe", apply(ctx) {\n'
            '  let probe = 0;\n'
            '  ctx.inject(["tui"], c => {\n'
            '    c.tui.status.add({ render: () => "MODEL TEST READY" });\n'
            '    c.tui.keymap.add({ f9: () => c.interaction.notify("zh: " + c.tui.command.available("model-manager:preset-zh") + " zm: " + c.tui.command.available("model-manager:preset-zm") + " lm: " + c.tui.command.available("model-manager:preset-lm")), f7: async () => { await plugins.dispose("model-manager"); plugins.use(manager()); }, f8: async () => {\n'
            '      const id = currentPane()?.session.sessionId;\n'
            '      if (!id) return;\n'
            '      const entry = await client.sessionGet(id);\n'
            '      c.interaction.notify("P" + (++probe) + " " + entry.session.model + " [" + entry.session.reasoning + "]");\n'
            '    }});\n'
            '  });\n'
            '}});\n'
        )
        (profile / "providers.json").write_text(json.dumps({"providers": [{
            "id": "manager-test", "base_url": f"http://127.0.0.1:{server.server_port}/v1",
            "endpoints": [{"protocol": "openai_chat"}],
            "models": [{"id": name, "upstream_id": name, "reasoning_levels": levels,
                        "flags": {"thinking_format": "openai"},
                        "limits": {"context_window": 100000, "max_output_tokens": 4096}}
                       for name, levels in (("zeta", ["low", "medium", "high"]),
                                            ("middle", ["low", "medium", "high", None]),
                                            ("alpha", ["low"]))],
        }]}))
        (profile / "providers.json").chmod(0o600)
        environment = {"HOME": str(root), "PATH": os.environ["PATH"], "SHELL": "/bin/bash",
                       "TERM": "xterm-256color", "YUKE_APPNAME": "yuke"}
        for key in ("CONFIG", "DATA", "STATE", "CACHE"):
            environment[f"XDG_{key}_HOME"] = str(root / key.lower())
        run = root / "run.sh"
        run.write_text("#!/bin/sh\ncd " + shlex.quote(str(root / "workspace")) + "\nexec env -i " +
                       " ".join(shlex.quote(k + "=" + v) for k, v in environment.items()) + " " + shlex.quote(YUKE) + "\n")
        run.chmod(0o700)
        tmux("new-session", "-d", "-x", "120", "-y", "32", "-s", "test", str(run))
        expect("startup", "MODEL TEST READY")
        command("/model")
        expect("model names and favorite markers", "1) ★ middle", "2) ★ alpha", "3) zeta", "alias mh", "alias bad", absent=("1) /mh", "2) /missing", "3) /bad", "unavailable"))
        keys("Escape")
        command("/model manager-test/middle")
        expect("model only, no effort dialog", "manager-test/middle", absent=("select a model", "middle · effort"))
        command("/effort")
        expect("numbered effort", "1) low", "2) medium", "3) high", "4) off")
        keys("3")
        expect("draft high", "manager-test/middle · high", absent=("middle · effort",))
        command("create test session")
        expect("first response", "Model manager test reply.")
        persisted("draft choice persisted", "manager-test/middle", "high")
        command("/model 3")
        expect("model retains supported effort", "manager-test/zeta · high")
        persisted("model choice persisted", "manager-test/zeta", "high")
        command("/effort 2")
        expect("effort only", "manager-test/zeta · medium")
        persisted("effort choice persisted", "manager-test/zeta", "medium")
        command("/mh")
        expect("quick alias", "manager-test/middle · high")
        command("/model")
        expect("favorites remain model rows", "1) ★ middle", "2) ★ alpha", "3) zeta")
        keys("Escape")
        command("/bad")
        expect("reject unsupported preset effort", "Unsupported effort high for alpha")
        persisted("rejected preset preserves choice", "manager-test/middle", "high")
        command("/effort off")
        persisted("off effort persisted", "manager-test/middle", "off")
        command("/effort")
        expect("off label", "4) off", "current")
        keys("4")
        command("/missing")
        expect("missing selector warning", "No model for /missing: manager-test/missing")
        command("/model alpha")
        expect("unsupported previous effort uses model default", "manager-test/alpha · low")
        command("/effort high")
        expect("invalid effort warning", "Unknown effort. Choose: low")
        keys("C-x", "h")
        expect("preset shortcut", "manager-test/middle · high")
        literal("unsent draft")
        keys("C-x", "m")
        expect("model shortcut preserves draft", "select a model", "unsent draft")
        literal("zeta")
        expect("filtered row numbers", "1) zeta", absent=("2) middle",))
        keys("1")
        expect("model selection opens effort step", "zeta · effort", "1) low", "3) high", "unsent draft")
        keys("Escape")
        persisted("cancel effort preserves previous model", "manager-test/middle", "high")
        keys("C-x", "m")
        expect("reopen combined picker", "select a model", "unsent draft")
        literal("zeta")
        expect("filter again", "1) zeta")
        keys("1")
        expect("effort step before apply", "zeta · effort", "unsent draft")
        keys("3")
        expect("effort confirmation applies model", "manager-test/zeta · high", "unsent draft", absent=("zeta · effort",))
        keys("C-x", "e")
        expect("effort shortcut preserves draft", "zeta · effort", "unsent draft")
        keys("Escape")
        keys("C-u")
        command("/mh")
        command("verify next turn")
        deadline = time.monotonic() + 10
        while len(REQUESTS) < 2 and time.monotonic() < deadline:
            time.sleep(0.05)
        assert len(REQUESTS) == 2, REQUESTS
        assert REQUESTS[0]["model"] == "middle", REQUESTS[0]
        assert REQUESTS[0]["reasoning_effort"] == "high", REQUESTS[0]
        assert REQUESTS[1]["model"] == "middle", REQUESTS[1]
        assert REQUESTS[1]["reasoning_effort"] == "high", REQUESTS[1]
        assert not ERRORS, ERRORS
        expect("second response", "verify next turn", "Model manager test reply.")
        providers = json.loads((profile / "providers.json").read_text())
        for name in ("gpt-6-sol", "gpt-6.1-sol", "gpt-6.9-sol", "gpt-6.10-sol", "gpt-99-sol-pro", "gpt-6.1-luna"):
            providers["providers"][0]["models"].append({
                "id": name, "upstream_id": name, "reasoning_levels": ["low", "medium", "high"],
                "flags": {"thinking_format": "openai"},
            })
        providers["providers"].append({
            "id": "other-test", "base_url": f"http://127.0.0.1:{server.server_port}/v1",
            "endpoints": [{"protocol": "openai_chat"}],
            "models": [{"id": "gpt-100-sol", "upstream_id": "gpt-100-sol", "reasoning_levels": ["high"]}],
        })
        (profile / "providers.json").write_text(json.dumps(providers))
        command("/sh")
        persisted("numeric latest version, no pro or other provider", "manager-test/gpt-6.10-sol", "high")
        command("/lm")
        persisted("latest Luna medium", "manager-test/gpt-6.1-luna", "medium")
        command("/model")
        expect("latest favorites are marked model names", "3) ★ gpt-6.10-sol", "4) ★ gpt-6.1-luna", "alias sh", "alias lm", absent=("3) /sh", "4) /lm"))
        keys("3")
        expect("favorite selection opens effort step", "gpt-6.10-sol · effort", "3) high", "suggested")
        keys("3")
        persisted("numbered latest favorite", "manager-test/gpt-6.10-sol", "high")
        providers["providers"][0]["models"].append({
            "id": "gpt-7.2-sol", "upstream_id": "gpt-7.2-sol", "reasoning_levels": ["medium", "high"],
            "flags": {"thinking_format": "openai"},
        })
        (profile / "providers.json").write_text(json.dumps(providers))
        keys("C-x", "s")
        persisted("preset shortcut follows new catalog version", "manager-test/gpt-7.2-sol", "high")
        keys("C-x", "l")
        persisted("Luna preset shortcut", "manager-test/gpt-6.1-luna", "medium")
        assert len(REQUESTS) == 2, "preset changes must not send a model request"
        command("/model")
        expect("editable model list", "select a model", "Ctrl+A alias", "Ctrl+R remove")
        literal("zeta")
        expect("plain model before alias", "1) zeta", absent=("★ zeta",))
        keys("C-a")
        expect("alias input", "Alias for zeta", "Short name")
        literal("zh")
        keys("Enter")
        expect("new alias favorite row", "1) ★ zeta", "alias zh · medium")
        saved = json.loads((profile / "model-aliases.json").read_text())
        assert saved["revision"] == 1, saved
        assert next(row for row in saved["presets"] if row["alias"] == "zh")["model"] == "manager-test/zeta"
        keys("C-e")
        expect("alias effort editor", "zeta · alias effort", "1) low", "3) high")
        keys("3")
        expect("updated alias effort", "1) ★ zeta", "alias zh · high")
        keys("Escape")
        persisted("editing aliases does not select a model", "manager-test/gpt-6.1-luna", "medium")
        command("/zh")
        persisted("new slash alias applies", "manager-test/zeta", "high")
        command("/model")
        expect("rename list", "select a model")
        literal("zeta")
        expect("rename selected favorite", "1) ★ zeta", "alias zh · high")
        keys("C-a")
        expect("rename input", "Alias for zeta", "Current: /zh")
        literal("mh")
        keys("Enter")
        expect("duplicate rejected", "Cannot save model aliases:", "alias zh · high")
        assert any(row["alias"] == "zh" for row in json.loads((profile / "model-aliases.json").read_text())["presets"])
        keys("C-a")
        expect("rename again", "Alias for zeta")
        literal("zm")
        keys("Enter")
        expect("renamed favorite", "1) ★ zeta", "alias zm · high", absent=("alias zh · high",))
        keys("Escape")
        keys("F9")
        expect("old alias command removed", "zh: false zm: true")
        keys("F7")
        time.sleep(0.2)
        command("/model")
        expect("reload alias list", "select a model")
        literal("zeta")
        expect("alias survives plugin reload", "1) ★ zeta", "alias zm · high")
        keys("Escape")
        tmux("kill-session", "-t", "test")
        tmux("new-session", "-d", "-x", "120", "-y", "32", "-s", "test", str(run))
        expect("restart", "MODEL TEST READY")
        command("/model")
        expect("restart list", "select a model")
        literal("zeta")
        expect("alias survives process restart", "1) ★ zeta", "alias zm · high")
        keys("C-r")
        expect("confirm alias removal", "Remove alias /zm?", "The model stays in the list")
        keys("Enter")
        expect("removed alias leaves normal model row", "1) zeta", absent=("★ zeta", "alias zm · high"))
        keys("Escape")
        keys("F9")
        expect("removed aliases have no commands", "zh: false zm: false")
        saved = json.loads((profile / "model-aliases.json").read_text())
        assert saved["revision"] == 4, saved
        assert not any(row["alias"] in ("zh", "zm") for row in saved["presets"]), saved
        assert (profile / "model-aliases.json").stat().st_mode & 0o777 == 0o600
        keys("F7")
        time.sleep(0.2)
        command("/model")
        expect("removal survives reload", "select a model")
        literal("zeta")
        expect("no favorite restored from defaults", "1) zeta", absent=("★ zeta", "alias zm"))
        keys("C-u")
        literal("lm")
        expect("initial favorite before removal", "1) ★ gpt-6.1-luna", "alias lm · medium")
        keys("C-r")
        expect("remove initial alias", "Remove alias /lm?")
        keys("Enter")
        expect("initial alias removed", "select a model", absent=("★ gpt-6.1-luna", "alias lm · medium"))
        keys("Escape")
        keys("F7")
        time.sleep(0.2)
        keys("F9")
        expect("initial alias does not return on reload", "zh: false zm: false lm: false")
        saved = json.loads((profile / "model-aliases.json").read_text())
        assert saved["revision"] == 5 and not any(row["alias"] == "lm" for row in saved["presets"]), saved
        keys("C-x", "s")
        expect("saved family alias keeps following latest", "manager-test/gpt-7.2-sol · high")
        assert len(REQUESTS) == 2, "alias management must not send a model request"
finally:
    tmux("kill-server", check=False)
    server.shutdown()
    with tempfile.NamedTemporaryFile(prefix="yuke-model-manager-", suffix=".txt", mode="w", delete=False) as artifact:
        artifact.write("\n".join(CAPTURES))
        artifact.write("\nRequest model/effort: " + json.dumps([
            {"model": value.get("model"), "effort": value.get("reasoning_effort")} for value in REQUESTS]))
        print("Saved model manager captures:", artifact.name)

print("Model manager TUI check passed")
