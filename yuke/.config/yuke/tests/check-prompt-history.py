#!/usr/bin/env python3
"""Check prompt history, unsent-draft restoration, Ctrl keys, and working-strip composition."""
import json
import pathlib
import shutil
import subprocess
import tempfile
import time
import uuid

TMUX = shutil.which("tmux")
YUKE = shutil.which("yuke")
assert TMUX, "tmux is required"
assert YUKE, "yuke is required"
profile_root = pathlib.Path(__file__).resolve().parents[1]
plugin = profile_root / "plugins" / "prompt-history.js"
vim_plugin = profile_root / "plugins" / "vim-improved.js"
session = "yuke-prompt-history-" + uuid.uuid4().hex[:10]
transcript = []


def tmux(*args, check=True):
    return subprocess.run(
        [TMUX, *args], check=check, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )


def capture(target, label):
    screen = tmux("capture-pane", "-t", target, "-p", "-S", "-28").stdout
    transcript.append(f"=== {label} ===\n{screen}")
    return screen


def wait_screen(target, label, text, timeout=5):
    deadline = time.monotonic() + timeout
    screen = ""
    while time.monotonic() < deadline:
        screen = capture(target, label)
        if text in screen:
            return screen
        transcript.pop()
        time.sleep(0.05)
    raise AssertionError(f"timed out at {label}, wanted {text!r}\n{screen}")


def send(target, *keys, literal=None):
    if literal is not None:
        tmux("send-keys", "-t", target, "-l", literal)
    else:
        tmux("send-keys", "-t", target, *keys)


try:
    with tempfile.TemporaryDirectory(prefix="yuke-prompt-history-") as directory:
        root = pathlib.Path(directory)
        profile = root / "config" / "yuke"
        profile.mkdir(parents=True)
        (profile / "index.js").write_text(
            'import { plugins } from "yuke";\n'
            'import { currentPane } from "yuke:session";\n'
            f'import {{ vimImproved }} from {json.dumps(str(vim_plugin))};\n'
            f'import {{ promptHistory }} from {json.dumps(str(plugin))};\n'
            'plugins.use(vimImproved);\n'
            'plugins.use(promptHistory);\n'
            'plugins.use({ name: "prompt-history-fixture", apply(ctx) {\n'
            '  ctx.inject(["tui"], (c) => {\n'
            '    const view = currentPane(); if (!view) throw new Error("no current pane");\n'
            '    const parts = new Map([\n'
            '      [1, [{ id: 0, type: "text", text: "first old prompt " }, { id: 1, type: "image", source: { hash: "test-image", mime: "image/png", bytes: 42 } }]],\n'
            '      [2, [{ id: 0, type: "text", text: "first answer" }]],\n'
            '      [3, [{ id: 0, type: "text", text: "second old prompt" }]],\n'
            '      [4, [{ id: 0, type: "text", text: "second answer" }]],\n'
            '    ]);\n'
            '    view.transcript.partsOf = (id) => parts.get(id) || [];\n'
            '    view.transcript.setOutline([\n'
            '      { id: 1, type: "user" }, { id: 2, type: "assistant" },\n'
            '      { id: 3, type: "user" }, { id: 4, type: "assistant" },\n'
            '    ], null);\n'
            '    view.session.activity = { state: { type: "waiting", run_id: "test", started_at_ms: 1 }, queued: 1, context_tokens: 0 };\n'
            '    c.on("chat.strip", () => [{ text: "queued  later prompt", group: "UIDim" }]);\n'
            '    c.tui.keymap.add({ f5: () => { view.composer.text = ""; return true; }, f6: "prompt-history:show" });\n'
            '    c.tui.status.add({ side: "left", render: () => view.composer.content().some((part) => part.type === "image" && part.source.hash === "test-image") ? "IMAGE RESTORED" : "" });\n'
            '    c.tui.root.invalidate();\n'
            '  });\n'
            '} });\n'
        )
        run = root / "run.sh"
        run.write_text(
            "#!/bin/sh\n"
            f"export XDG_CONFIG_HOME={json.dumps(str(root / 'config'))}\n"
            f"export XDG_DATA_HOME={json.dumps(str(root / 'data'))}\n"
            f"export XDG_STATE_HOME={json.dumps(str(root / 'state'))}\n"
            f"export XDG_CACHE_HOME={json.dumps(str(root / 'cache'))}\n"
            "export TERM=xterm-256color\n"
            f"exec {json.dumps(YUKE)}\n"
        )
        run.chmod(0o700)
        tmux("new-session", "-d", "-x", "100", "-y", "28", "-s", session, str(run))
        target = tmux("list-panes", "-t", session, "-F", "#{pane_id}").stdout.strip()

        screen = wait_screen(target, "initial working strip", "working  second old prompt")
        assert "queued  later prompt" in screen
        assert screen.index("queued  later prompt") < screen.index("working  second old prompt"), "working prompt must render below queued prompts"
        assert "NORMAL" in screen

        send(target, "i")
        send(target, literal="half written draft")
        wait_screen(target, "insert-mode draft", "› half written draft")

        send(target, "Up")
        wait_screen(target, "insert arrow up newest", "› second old prompt")
        send(target, "Up")
        screen = wait_screen(target, "insert arrow up oldest", "› first old prompt")
        assert "IMAGE RESTORED" in screen, "history recall dropped the image attachment"
        send(target, "Down")
        wait_screen(target, "insert arrow down newer", "› second old prompt")
        send(target, "Down")
        screen = wait_screen(target, "insert arrow down restores draft", "› half written draft")
        assert "INSERT" in screen

        send(target, "C-k")
        wait_screen(target, "insert Ctrl+K recalls newest", "› second old prompt")
        send(target, "C-j")
        send(target, literal="continued after recall")
        screen = wait_screen(target, "insert Ctrl+J newline after recall", "  continued after recall")
        assert "› second old prompt" in screen and "INSERT" in screen

        send(target, "F5")
        send(target, literal="half written draft")
        wait_screen(target, "reset insert draft", "› half written draft")
        send(target, "C-j")
        send(target, literal="second line")
        wait_screen(target, "multiline insert draft", "  second line")
        send(target, "Up")
        time.sleep(0.1)
        screen = capture(target, "insert arrow keeps multiline motion")
        assert "› half written draft" in screen and "  second line" in screen
        send(target, "Up")
        wait_screen(target, "insert arrow at top opens history", "› second old prompt")
        send(target, "Down")
        screen = wait_screen(target, "insert arrow restores multiline draft", "› half written draft")
        assert "  second line" in screen

        send(target, "Escape")
        wait_screen(target, "normal-mode draft", "▪ half written draft")
        send(target, "Up")
        wait_screen(target, "normal arrow up newest", "▪ second old prompt")
        send(target, "Up")
        wait_screen(target, "arrow up oldest", "▪ first old prompt")
        send(target, "Down")
        wait_screen(target, "arrow down newer", "▪ second old prompt")
        send(target, "Down")
        wait_screen(target, "arrow down restores draft", "▪ half written draft")

        started = time.monotonic()
        send(target, "C-k")
        screen = wait_screen(target, "Ctrl+K newest immediately", "▪ second old prompt", timeout=0.5)
        assert time.monotonic() - started < 0.8, "Ctrl+K waited for the chord timeout"
        assert "ctrl+k" not in screen.lower(), "Ctrl+K left a pending chord"
        started = time.monotonic()
        send(target, "C-j")
        screen = wait_screen(target, "Ctrl+J restores draft immediately", "▪ half written draft", timeout=0.5)
        assert time.monotonic() - started < 0.8, "Ctrl+J was delayed"
        assert "NORMAL" in screen

        send(target, "F5")
        send(target, "/")
        send(target, literal="history")
        send(target, "Enter")
        screen = wait_screen(target, "/history picker", "Prompt history")
        assert "first old prompt" in screen and "second old prompt" in screen
        send(target, "C-j")
        send(target, "Enter")
        screen = wait_screen(target, "picker Ctrl+J selects older prompt", "▪ first old prompt")
        assert "Prompt history" not in screen and "IMAGE RESTORED" in screen, "picker recall dropped the image attachment"

        send(target, "F6")
        wait_screen(target, "reopened prompt history picker", "Prompt history")
        send(target, "C-j")
        send(target, "C-k")
        send(target, "Enter")
        screen = wait_screen(target, "picker Ctrl+K selects newer prompt", "▪ second old prompt")
        assert "Prompt history" not in screen
finally:
    tmux("kill-session", "-t", session, check=False)
    with tempfile.NamedTemporaryFile(prefix="yuke-prompt-history-", suffix=".txt", mode="w", delete=False) as artifact:
        artifact.write("\n".join(transcript))
        print("Saved prompt history transcript:", artifact.name)

print("Prompt history tmux check passed")
