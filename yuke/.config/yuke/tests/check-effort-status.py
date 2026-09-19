#!/usr/bin/env python3
"""Check that the selected reasoning effort follows the model in an isolated TUI."""
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
plugin = pathlib.Path(__file__).resolve().parents[1] / "plugins" / "effort-status.js"
socket = "yuke-effort-status-" + uuid.uuid4().hex[:10]
transcript = []


def tmux(*args, check=True):
    return subprocess.run(
        [TMUX, "-L", socket, *args], check=check, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )


def capture(label):
    screen = tmux("capture-pane", "-t", "test", "-p", "-S", "-28").stdout
    transcript.append(f"=== {label} ===\n{screen}")
    return screen


try:
    with tempfile.TemporaryDirectory(prefix="yuke-effort-status-") as directory:
        root = pathlib.Path(directory)
        profile = root / "config" / "yuke"
        profile.mkdir(parents=True)
        (profile / "index.js").write_text(
            'import { client, plugins } from "yuke";\n'
            'import { Session, currentPane } from "yuke:session";\n'
            f'import {{ effortStatus }} from {json.dumps(str(plugin))};\n'
            'plugins.use({ name: "effort-status-probe", apply(ctx) {\n'
            '  ctx.advise(client, "sessionGet", "around", (_next, id) => Promise.resolve(\n'
            '    /** @type {any} */ ({ session: { id, reasoning: "high" } })\n'
            '  ));\n'
            '  ctx.advise(Session.prototype, "modelSelector", "filterReturn", () => "probe/model");\n'
            '  ctx.inject(["tui"], () => {\n'
            '    const pane = currentPane();\n'
            '    if (!pane) throw new Error("no current chat pane");\n'
            '    pane.session.sessionId = "probe-session";\n'
            '  });\n'
            '}});\n'
            '// Load after the session choice to exercise the persisted-session fallback.\n'
            'plugins.use(effortStatus);\n'
        )
        run = root / "run.sh"
        run.write_text(
            "#!/bin/sh\n"
            f"export XDG_CONFIG_HOME={json.dumps(str(root / 'config'))}\n"
            f"export XDG_DATA_HOME={json.dumps(str(root / 'data'))}\n"
            f"export XDG_STATE_HOME={json.dumps(str(root / 'state'))}\n"
            f"export XDG_CACHE_HOME={json.dumps(str(root / 'cache'))}\n"
            "unset HERDR_ENV HERDR_PANE_ID HERDR_SOCKET_PATH\n"
            "export TERM=xterm-256color\n"
            f"exec {json.dumps(YUKE)}\n"
        )
        run.chmod(0o700)
        tmux("new-session", "-d", "-x", "100", "-y", "28", "-s", "test", str(run))

        deadline = time.monotonic() + 5
        screen = ""
        while time.monotonic() < deadline:
            screen = capture("selected model and effort")
            if "probe/model · high" in screen:
                break
            transcript.pop()
            time.sleep(0.05)
        else:
            raise AssertionError(f"effort did not follow the model in the status bar\n{screen}")
finally:
    tmux("kill-server", check=False)
    with tempfile.NamedTemporaryFile(prefix="yuke-effort-status-", suffix=".txt", mode="w", delete=False) as artifact:
        artifact.write("\n".join(transcript))
        print("Saved effort status transcript:", artifact.name)

print("Effort status tmux check passed")
