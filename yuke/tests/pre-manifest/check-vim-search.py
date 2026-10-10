#!/usr/bin/env python3
"""Check the draft search dialog in an isolated pseudo-terminal. Do not use desktop input."""
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
with tempfile.TemporaryDirectory(prefix="yuke-vim-search-") as directory:
    profile = pathlib.Path(directory) / "yuke"
    profile.mkdir()
    source = r'''
import { plugins } from "yuke";
import { quit } from "yuke:ui";
import { vimImproved } from PLUGIN;
plugins.use(vimImproved);
plugins.use({ name: "search-dialog-check", apply(ctx) {
 ctx.inject(["tui", "composer-vim"], c => {
  const view = c.tui.root.active, input = view.composer.input;
  input.setText("one two one"); c["composer-vim"].setMode(view.composer, "normal"); input.caret = 0;
  function assert(ok, message) { if (!ok) throw Error(message); }
  function key(char, mods = 0, code = "char") { c.tui.root.onEvent({ type: "key", code, char, text: mods ? "" : char, event: "press", mods, shifted: "", baseLayout: "" }); }
  function press(value) { for (const char of value) key(char); }
  setTimeout(() => {
   key("/", 2);
   assert(c.tui.root.overlays.length > 0, "search opens a real modal");
   press("/"); assert(input.text === "one two one", "modal slash cannot edit the composer");
   key("u", 4); press("one"); key("", 0, "enter");
   setTimeout(() => {
    assert(input.caret === 8 && input.text === "one two one", "search finds the next literal occurrence");
    press("n"); assert(input.caret === 0, "search wraps");
    press("N"); assert(input.caret === 8, "reverse repeat follows the saved search");
    key("/", 2); key("", 0, "esc");
    setTimeout(() => {
     assert(input.caret === 8, "cancel keeps the caret");
     key("/", 2); press("missing"); key("", 0, "enter");
     setTimeout(() => {
      assert(input.caret === 8 && input.text === "one two one", "missing search keeps the draft and caret");
      input.setText("e\u0301 e\u0301"); input.caret = 0;
      key("/", 2); key("\u0301"); key("", 0, "enter");
      setTimeout(() => {
       assert(input.caret === 0, "search cannot stop inside a grapheme");
       c.tui.status.add({ side: "left", render: () => "SEARCH-PASSED" });
       c.tui.root.invalidate();
       setTimeout(() => quit(), 500);
      }, 50);
     }, 50);
    }, 50);
   }, 50);
  }, 200);
 });
}});
'''
    (profile / "index.js").write_text(source.replace("PLUGIN", json.dumps(str(plugin))))
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
    with tempfile.NamedTemporaryFile(prefix="yuke-vim-search-", suffix=".ansi", delete=False) as artifact:
        artifact.write(output)
        print("Saved render:", artifact.name)
    assert code == 0, f"yuke exited with {code}"
    assert b"SEARCH-PASSED" in output, "the search checks must finish"
    print("Draft search dialog check passed")
