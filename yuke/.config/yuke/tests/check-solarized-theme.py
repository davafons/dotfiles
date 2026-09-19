#!/usr/bin/env python3
"""Check theme contrast, palette changes, and rendered colors without desktop input."""
import fcntl
import json
import os
import pathlib
import pty
import re
import select
import shlex
import shutil
import struct
import subprocess
import tempfile
import termios
import time
import uuid

YUKE = shutil.which("yuke")
TMUX = shutil.which("tmux")
assert YUKE and TMUX, "yuke and tmux are required"
plugin = pathlib.Path(__file__).resolve().parents[1] / "plugins" / "solarized-theme.js"
artifact = pathlib.Path(tempfile.mkdtemp(prefix="yuke-solarized-check-"))

PROFILE = '''
import { plugins, defineConfig } from "yuke";
import { Window, Pager, keys } from "yuke:ui";
import { Transcript } from "yuke:chat";
import { solarizedTheme } from PLUGIN;
defineConfig({ colors: COLORS });
plugins.use(solarizedTheme);
plugins.use({ name: "theme-probe", apply(ctx) {
  ctx.inject(["tui"], c => {
    const names = ["MdText", "MdHeading", "MdCode", "MdCodeBlock", "MdQuote", "UIDim",
      "UIItemSel", "UIDimSel", "UIComposerPrompt", "UIComposerPlaceholder", "YukeStatus", "YukeBar", "YukeRule", "YukeEmpty",
      "TxUser", "TxMeta", "TxThought", "TxToolTitle", "TxToolArg", "TxToolOutput", "TxToolHint",
      "TxToolPendingBg", "TxToolSuccessBg", "TxToolErrorBg", "TxToolError", "TxDiffAdd", "TxDiffDel", "TxDiffContext"];
    const snapshot = () => {
      const json = JSON.stringify({
        colors: c.tui.colors, background: c.tui.background, palette: c.tui.style.palette,
        groups: Object.fromEntries(names.map(name => [name, c.tui.style.resolve(name)])),
      });
      for (let at = 0; at < json.length; at += 700) ctx.print("THEME_CHUNK " + json.slice(at, at + 700));
      ctx.print("THEME_SNAPSHOT_DONE");
    };
    snapshot();
    c.on("colors.changed", snapshot);
    c.on("background.changed", snapshot);
    c.tui.command.add("depth", { run() {
      defineConfig({ colors: c.tui.colors === "truecolor" ? "256" : "truecolor" });
    }});
    c.tui.keymap.add({ "alt+c": "theme-probe:depth" });
    const pager = new Pager();
    pager.setRows([
      { text: "Solarized theme preview", group: "MdHeading" },
      { text: "Body text stays neutral for reading.", group: "MdText" },
      { text: "User message", group: "TxUser", bg: "TxUser" },
      { text: "Reasoning uses violet.", group: "TxThought" },
      { segments: [{ text: "read ", group: "TxToolTitle" }, { text: "src/main.zig", group: "TxToolArg" }], bg: "TxToolSuccessBg" },
      { text: "Tool output stays readable.", group: "TxToolOutput", bg: "TxToolSuccessBg" },
      { text: "Inline code uses yellow.", group: "MdCode" },
      { text: "const answer = 42;", group: "MdCodeBlock" },
      { text: "+ Added line", group: "TxDiffAdd", bg: "TxDiffAdd" },
      { text: "- Deleted line", group: "TxDiffDel", bg: "TxDiffDel" },
      { text: "Errors stay red.", group: "TxToolError", bg: "TxToolErrorBg" },
      { text: "Hints stay readable.", group: "TxToolHint" },
    ]);
    let rect = { x: 0, y: 0, w: 0, h: 0 };
    let close = () => {};
    const win = new Window({ title: "Theme check", width: 76, height: 18, content: {
      layout(bounds) { rect = bounds; },
      draw() { pager.draw(rect); },
      onKey(ev) { if (ev.code === "esc") close(); return true; },
    }});
    close = c.tui.overlay(win);
    c.tui.command.add("history", { run() {
      const outline = [];
      const parts = new Map();
      for (let turn = 0; turn < 4; turn++) {
        const user = turn * 2 + 1;
        const assistant = user + 1;
        outline.push({ id: user, type: "user" }, { id: assistant, type: "assistant" });
        parts.set(user, [{ type: "text", id: 0, text: "Request " + turn + ": inspect the theme.\\nKeep the foreground blue." }]);
        parts.set(assistant, [
          { type: "text", id: 0, text: "## Work block " + turn + "\\nBody text and `inline code`." },
          { type: "tool", id: 1, call_id: "preview-" + turn, name: "read", arguments: '{"path":"theme.js"}',
            state: { type: "completed", duration_ms: 12, output: "Completed work " + turn + "\\nForeground blue is preserved.\\nThe tool block has a soft background." } },
          { type: "text", id: 2, text: "Result " + turn + ": contrast is readable." },
        ]);
      }
      const history = new Transcript({ partsOf: id => parts.get(id) || [] });
      history.setOutline(outline, null);
      for (let turn = 0; turn < 4; turn++) history.togglePart(turn * 2 + 2, 1);
      history.pager.toTop();
      let bounds = { x: 0, y: 0, w: 0, h: 0 };
      let dismiss = () => {};
      dismiss = c.tui.overlay(new Window({ title: "History check", width: 76, height: 18, content: {
        layout(rect) { bounds = rect; },
        draw() { history.pager.draw(bounds); },
        onKey(ev) {
          const stroke = keys.strokeOf(ev);
          if (stroke === "esc") dismiss();
          else if (stroke === "j") history.pager.navPage(1);
          else if (stroke === "k") history.pager.navPage(-1);
          c.tui.root.invalidatePaint();
          return true;
        },
      }}));
    }});
    c.tui.keymap.add({ "alt+h": "theme-probe:history" });
  });
}});
'''


def profile(root, colors):
    directory = root / "config" / "yuke"
    directory.mkdir(parents=True)
    (directory / "index.js").write_text(
        PROFILE.replace("PLUGIN", json.dumps(str(plugin))).replace("COLORS", json.dumps(colors))
    )
    env = os.environ.copy()
    for name, suffix in [("XDG_CONFIG_HOME", "config"), ("XDG_DATA_HOME", "data"),
                         ("XDG_STATE_HOME", "state"), ("XDG_CACHE_HOME", "cache")]:
        env[name] = str(root / suffix)
    env.update(TERM="xterm-256color", COLORTERM="truecolor", YUKE_APPNAME="yuke")
    for name in ["HERDR_ENV", "HERDR_PANE_ID", "HERDR_SOCKET_PATH"]:
        env.pop(name, None)
    return env


def snapshots(root):
    result = []
    for log in (root / "state").rglob("*.log"):
        chunks = []
        for line in log.read_text(errors="replace").splitlines():
            if "THEME_CHUNK " in line:
                chunks.append(line.split("THEME_CHUNK ", 1)[1])
            elif "THEME_SNAPSHOT_DONE" in line:
                result.append(json.loads("".join(chunks)))
                chunks = []
    return result


def luminance(color):
    if isinstance(color, str):
        channels = [int(color[i:i + 2], 16) for i in (1, 3, 5)]
    elif color >= 232:
        channels = [8 + (color - 232) * 10] * 3
    else:
        assert color >= 16, "the theme must not depend on remapped ANSI colors"
        levels = [0, 95, 135, 175, 215, 255]
        n = color - 16
        channels = [levels[n // 36], levels[n // 6 % 6], levels[n % 6]]
    linear = [v / 255 / 12.92 if v / 255 <= 0.04045 else ((v / 255 + 0.055) / 1.055) ** 2.4
              for v in channels]
    return sum(v * weight for v, weight in zip(linear, [0.2126, 0.7152, 0.0722]))


def background_sgr(color):
    return "48;2;" + ";".join(str(int(color[i:i + 2], 16)) for i in (1, 3, 5))


def check(snapshot):
    groups = snapshot["groups"]
    pairs = [(name, name) for name in groups if not name.endswith("Bg")]
    pairs += [(name, background) for name in ["TxToolTitle", "TxToolArg", "TxToolOutput", "TxToolHint",
                                            "TxDiffAdd", "TxDiffDel", "TxDiffContext"]
              for background in ["TxToolPendingBg", "TxToolSuccessBg", "TxToolErrorBg"]]
    pairs.append(("TxMeta", "TxUser"))
    minimum = 100
    for name, background in pairs:
        style = groups[name]
        assert not style.get("dim"), name + " must use a readable explicit color"
        fg = style["fg"]
        bg = groups[background].get("bg", snapshot["palette"]["bg"])
        low, high = sorted([luminance(fg), luminance(bg)])
        ratio = (high + 0.05) / (low + 0.05)
        assert ratio >= 4.5, f"{name} on {background}: {ratio:.2f}:1"
        minimum = min(minimum, ratio)
    user_bg = luminance(groups["TxUser"]["bg"])
    tool_bg = luminance(groups["TxToolSuccessBg"]["bg"])
    base_bg = luminance(snapshot["palette"]["bg"])
    assert abs(user_bg - base_bg) > abs(tool_bg - base_bg), "requests must stand out more than completed work"
    print(f'{snapshot["colors"]}/{snapshot["background"]}: minimum reading contrast {minimum:.2f}:1')


for colors in ["truecolor", "256"]:
    for background in ["dark", "light"]:
        with tempfile.TemporaryDirectory(prefix="yuke-theme-pty-") as directory:
            root = pathlib.Path(directory)
            env = profile(root, colors)
            master, slave = pty.openpty()
            fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 30, 100, 0, 0))
            process = subprocess.Popen([YUKE], stdin=slave, stdout=slave, stderr=slave, env=env)
            os.close(slave)
            output = bytearray()
            try:
                deadline = time.monotonic() + 6
                while time.monotonic() < deadline:
                    ready, _, _ = select.select([master], [], [], 0.05)
                    if ready:
                        try:
                            chunk = os.read(master, 65536)
                        except OSError:
                            break
                        output.extend(chunk)
                        if b"\x1b]11;?" in chunk:
                            value = "082b/082b/082b" if background == "dark" else "fdfd/f6f6/e3e3"
                            os.write(master, ("\x1b]11;rgb:" + value + "\x1b\\").encode())
                    found = [s for s in snapshots(root) if s["background"] == background and s["colors"] == colors]
                    if found and b"Solarized theme preview" in output:
                        check(found[-1])
                        break
                else:
                    raise AssertionError(f"No rendered {colors}/{background} theme")
                (artifact / f"{colors}-{background}.ansi").write_bytes(output)
            finally:
                process.terminate()
                process.wait(timeout=5)
                os.close(master)


socket = "yuke-theme-" + uuid.uuid4().hex[:10]


def tmux(*args, check=True):
    return subprocess.run([TMUX, "-L", socket, *args], check=check, capture_output=True, text=True)


with tempfile.TemporaryDirectory(prefix="yuke-theme-tmux-") as directory:
    root = pathlib.Path(directory)
    env = profile(root, "truecolor")
    run = root / "run.sh"
    exports = ["export " + key + "=" + shlex.quote(env[key]) for key in env
               if key.startswith("XDG_") or key in ["TERM", "COLORTERM", "YUKE_APPNAME"]]
    run.write_text("#!/bin/sh\n" + "\n".join(exports) + "\nexec " + shlex.quote(YUKE) + "\n")
    run.chmod(0o700)
    try:
        tmux("-f", "/dev/null", "new-session", "-d", "-x", "100", "-y", "30", "-s", "theme", str(run))
        target = "theme:0.0"
        for _ in range(100):
            screen = tmux("capture-pane", "-p", "-e", "-t", target).stdout
            if "Solarized theme preview" in screen:
                break
            time.sleep(0.05)
        assert "Solarized theme preview" in screen, screen
        assert re.search(r"38;2;\d+;\d+;\d+", screen), "RGB colors must reach the terminal"
        (artifact / "tmux-preview.ansi").write_text(screen)
        tmux("send-keys", "-t", target, "Escape")
        tmux("send-keys", "-t", target, "M-h")
        for _ in range(100):
            screen = tmux("capture-pane", "-p", "-e", "-t", target).stdout
            if "Request 0:" in screen and "Completed work 0" in screen:
                break
            time.sleep(0.05)
        assert "Request 0:" in screen and "Completed work 0" in screen, screen
        resolved = snapshots(root)[-1]["groups"]
        user_sgr = background_sgr(resolved["TxUser"]["bg"])
        tool_sgr = background_sgr(resolved["TxToolSuccessBg"]["bg"])
        assert user_sgr in screen, "user-message background must reach the terminal"
        assert tool_sgr in screen, "completed-tool background must reach the terminal"
        (artifact / "tmux-history-top.ansi").write_text(screen)
        tmux("send-keys", "-t", target, "j")
        for _ in range(100):
            screen = tmux("capture-pane", "-p", "-e", "-t", target).stdout
            if "Request 0:" not in screen and "Completed work" in screen:
                break
            time.sleep(0.05)
        assert "Request 0:" not in screen and "Completed work" in screen, screen
        assert user_sgr in screen and tool_sgr in screen, "block backgrounds must survive scrolling"
        (artifact / "tmux-history-scrolled.ansi").write_text(screen)
        tmux("send-keys", "-t", target, "k")
        for _ in range(100):
            screen = tmux("capture-pane", "-p", "-t", target).stdout
            if "Request 0:" in screen:
                break
            time.sleep(0.05)
        assert "Request 0:" in screen, screen
        tmux("send-keys", "-t", target, "Escape")
        tmux("send-keys", "-t", target, "M-c")
        for _ in range(100):
            found = snapshots(root)
            if found and found[-1]["colors"] == "256":
                break
            time.sleep(0.05)
        assert found[-1]["colors"] == "256", "live palette switch did not apply"
        check(found[-1])
        tmux("send-keys", "-t", target, "C-p")
        for _ in range(100):
            screen = tmux("capture-pane", "-p", "-e", "-t", target).stdout
            if "/cache" in screen and "/compact" in screen:
                break
            time.sleep(0.05)
        assert "/cache" in screen and "/compact" in screen, screen
        (artifact / "tmux-command-palette.ansi").write_text(screen)
    finally:
        tmux("kill-server", check=False)

print("Theme rendering and live palette switch passed. Captures:", artifact)
