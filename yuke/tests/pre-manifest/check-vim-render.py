#!/usr/bin/env python3
"""Check visual selection in an isolated pseudo-terminal. Do not use desktop input."""
import fcntl
import json
import os
import pathlib
import pty
import select
import struct
import subprocess
import tempfile
import termios
import time

plugin = pathlib.Path(__file__).resolve().parents[1] / "plugins" / "vim-improved.js"
with tempfile.TemporaryDirectory(prefix="yuke-vim-render-") as directory:
    profile = pathlib.Path(directory) / "yuke"
    profile.mkdir()
    (profile / "index.js").write_text(
        'import { plugins } from "yuke";\n'
        'import { quit } from "yuke:ui";\n'
        f"import {{ vimImproved }} from {json.dumps(str(plugin))};\n"
        'plugins.use(vimImproved);\n'
        'plugins.use({ name: "visual-render-check", apply(ctx) {\n'
        '  ctx.inject(["tui", "composer-vim"], c => {\n'
        '    const view = c.tui.root.active;\n'
        '    view.composer.input.setText("alpha bravo");\n'
        '    c["composer-vim"].setMode(view.composer, "normal");\n'
        '    view.composer.input.caret = 0;\n'
        '    for (const char of "vll") c.tui.root.onEvent({ type: "key", code: "char",\n'
        '      char, text: char, event: "press", mods: 0, shifted: "", baseLayout: "" });\n'
        '    setTimeout(() => quit(), 700);\n'
        '  });\n'
        '}});\n'
    )
    env = os.environ.copy()
    env.update(
        XDG_CONFIG_HOME=directory,
        XDG_DATA_HOME=directory + "/data",
        XDG_STATE_HOME=directory + "/state",
        YUKE_APPNAME="yuke",
        TERM="xterm-256color",
        COLORTERM="truecolor",
    )
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 80, 0, 0))
    process = subprocess.Popen(["yuke"], stdin=slave, stdout=slave, stderr=slave, env=env)
    os.close(slave)
    output = bytearray()
    try:
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            ready, _, _ = select.select([master], [], [], 0.1)
            if ready:
                try:
                    chunk = os.read(master, 65536)
                except OSError:
                    break
                if not chunk:
                    break
                output.extend(chunk)
            elif process.poll() is not None:
                break
        if process.poll() is None:
            process.terminate()
        code = process.wait(timeout=5)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        os.close(master)
    with tempfile.NamedTemporaryFile(prefix="yuke-vim-render-", suffix=".ansi", delete=False) as artifact:
        artifact.write(output)
        print("Saved render:", artifact.name)
    assert code == 0, f"yuke exited with {code}"
    assert b"\x1b[7malp\x1b[27mha" in output, "the selected graphemes must use inverse style"
    assert b"VISUAL" in output, "the status must show visual mode"
    print("Visual selection render check passed")
