#!/usr/bin/env python3
"""Check the manifest profile in private homes with no provider credentials or model calls."""
import argparse
import errno
import fcntl
import json
import os
from pathlib import Path
import pty
import select
import shutil
import signal
import struct
import subprocess
import tempfile
import termios
import time

PROBE = r'''
//! Check the actual staged dispatcher, mode service, and owned reload cleanup.
import { env, fs } from "yuke";
import { ChatView } from "yuke:chat";
import { quit, ui, Window, Picker } from "yuke:ui";
/** Load an isolated test consumer. No TUI skips it. An invariant failure enters the captured log. @param {import("yuke").Context} ctx */
export default async function(ctx) {
  const tuiBorrow = ctx.get("tui"), vimBorrow = ctx.get("composer-vim");
  if (!tuiBorrow) { ctx.print("MIGRATION_HEADLESS"); return; }
  if (!vimBorrow) throw Error("missing Vim capability");
  const tui = tuiBorrow, vim = vimBorrow;
  const marker = ctx.root + "/disposed.json";
  const generation = await fs.stat(marker) ? JSON.parse(await fs.readFile(marker)) : 0;
  ctx.own(() => fs.writeFile(marker, JSON.stringify(generation + 1)));
  tui.keymap.add({ "ctrl+g": "reload" });
  /** @type {string[]} */ const transitions = [];
  ctx.on("composer-vim:mode", (_c, mode, previous) => transitions.push(previous + ">" + mode));
  ctx.once("ui.started", async () => { try {
    const root = tui.root, pane = root.active;
    if (!(pane instanceof ChatView)) throw Error("missing chat");
    const c = pane.composer;
    /** @param {unknown} actual @param {unknown} expected @param {string} label */
    function check(actual, expected, label) { if (JSON.stringify(actual) !== JSON.stringify(expected)) throw Error(label + ": " + JSON.stringify(actual) + " != " + JSON.stringify(expected)); }
    /** @param {string} char @param {number} [mods] @param {Parameters<import("yuke:ui").Tui["keymap"]["onKey"]>[0]["code"]} [code] */
    function key(char, mods = 0, code = "char") { root.onEvent({ type: "key", code, char, shifted: "", baseLayout: "", text: mods ? "" : char, mods, event: "press" }); }
    vim.setMode(c, "normal");
    if (generation) {
      check(c.text, "", "reload loses the draft");
      check(root.overlays.length, 0, "reload closes overlays");
      for (const name of ["models:effort", "controls:panel", "insights:status", "insights:usage"]) check(tui.command.available(name), false, "reload applies disabled feature " + name);
      transitions.length = 0; vim.setMode(c, "insert");
      check(transitions, ["normal>insert"], "one mode notification after reload");
      ctx.print("MIGRATION_RELOAD_PASS"); quit(); return;
    }
    const source = "0123456789".repeat(5) + "\nSECOND\nthird";
    const display = env.get("MIGRATION_ROWS") === "display";
    function reset() { c.input.setText(source); c.input.caret = 3; c.layout({ x: 0, y: 0, w: 12, h: 4 }); c.height(12); }
    reset(); key("j"); check(c.input.caret, display ? 13 : 54, "configured j");
    reset(); key("2"); key("j"); check(c.input.caret, display ? 23 : 61, "configured count");
    reset(); key("g"); key("j"); check(c.input.caret, 13, "explicit display motion");
    reset(); key("d"); check(vim.pending(c), true, "operator stays pending"); key("j"); check(c.text, "third", "operator remains logical");
    transitions.length = 0; vim.setMode(c, "normal"); check(transitions, [], "no event for same mode");
    key("v"); key("c"); key("", 0, "esc"); key("V"); vim.cancel(c);
    check(transitions, ["normal>visual", "visual>normal", "normal>insert", "insert>normal", "normal>visual-line", "visual-line>normal"], "all mode transitions");
    c.input.setText("abc def ghi"); c.input.caret = 0;
    for (const char of "yiwwviwPw.") key(char);
    check(c.text, "abc abc ", "native visual-put repeat");
    const image = { hash: "0".repeat(64), mime: "image/png", bytes: 1 };
    /** @type {ReturnType<ChatView["transcript"]["partsOf"]>} */
    const parts = [{ type: "text", id: 11, text: "previous prompt" }, { type: "image", id: 12, source: image }];
    pane.transcript.partsOf = () => parts;
    pane.transcript.setOutline([{ id: 1, type: "user" }], null);
    c.input.setText("unsent draft"); c.input.caret = 4;
    key("k", 4); check(c.hasImages(), true, "history keeps attachment"); check(c.text.startsWith("previous prompt"), true, "history beats window chord");
    key("j", 4); check(c.text, "unsent draft", "history returns draft"); check(c.input.caret, 4, "history returns caret"); check(c.hasImages(), false, "history clears recalled attachment");
    vim.setMode(c, "insert"); c.input.setText("one\ntwo"); c.input.caret = 0;
    key("", 0, "down"); check(c.input.caret > 0, true, "multiline arrow moves before history");
    const before = c.text; key("j", 4); check(c.text.length, before.length + 1, "insert Ctrl+J adds newline");
    c.input.setText("./folder/n");
    for (let i = 0; i < 40 && !root.overlays.some(layer => layer.name === "paths"); i++) await new Promise(done => setTimeout(done, 5));
    check(root.overlays.some(layer => layer.name === "paths"), true, "completion opens");
    check(vim.mode(c), "insert", "completion keeps insert mode");
    check(tui.keymap.pendingLabel(), "", "completion has no pending chord");
    key("", 0, "enter"); check(c.text, "./folder/nested.txt", "completion Enter does not submit");
    c.input.setText("./folder/"); vim.setMode(c, "normal");
    await new Promise(done => setTimeout(done, 30)); check(root.overlays.some(layer => layer.name === "paths"), false, "mode change rejects stale directory results");
    if (env.get("MIGRATION_CD") === "1") {
      vim.setMode(c, "insert");
      /** @returns {import("yuke:ui").Picker<{name: string, isDirectory: boolean}> | null} */
      function pathMenu() {
        const window = root.overlays.find(layer => layer.name === "paths");
        return window instanceof Window && window.content instanceof Picker ? window.content : null;
      }
      /** @param {string} value */
      async function directories(value) {
        c.text = value;
        for (let i = 0; i < 80 && !pathMenu(); i++) await new Promise(done => setTimeout(done, 5));
        const menu = pathMenu();
        if (!menu) throw Error("directory completion did not open for " + value);
        check(menu.source.every(entry => entry.isDirectory), true, "cd lists only directories");
        return menu;
      }
      check((await directories("/cd ")).source.some(entry => entry.name === "cd folder"), true, "empty cd lists directories");
      key("", 0, "tab");
      check(c.text, '/cd "./cd folder/"', "Tab quotes the directory and does not submit");
      await directories("/cd cd"); key("", 0, "enter");
      check(c.text, '/cd "./cd folder/"', "Enter completes a directory and does not submit");
      check((await directories("/cd ../")).source.some(entry => entry.name === "work"), true, "parent directory completion");
      check((await directories("/cd ~/")).source.some(entry => entry.name === "home-target"), true, "home directory completion");
      check((await directories("/cd /")).source.length > 0, true, "filesystem root completion");
      await directories("/cd 'cd"); key("", 0, "tab");
      check(c.text, "/cd './cd folder/'", "completion closes an existing quote");
      c.text = "./folder/"; vim.setMode(c, "normal");
      ctx.print("MIGRATION_CD_COMPLETION_PASS");
    }
    const modal = ui.pick({ title: "Modal priority", items: ["modal"], filter: false }); tui.overlay(modal.win);
    key("k", 4); check(c.text, "./folder/", "modal blocks history"); root.popOverlay(modal.win);
    c.input.setText("clear me"); key("c", 4); check(c.text, "", "Ctrl+C clears"); check(vim.mode(c), "normal", "Ctrl+C selects normal");
    check(tui.command.perform("controls:panel", "vsplit"), true, "panel command exists");
    check(root.root_node?.leaves().length, 2, "panel split"); tui.command.perform("controls:panel", "only"); check(root.root_node?.leaves().length, 1, "panel only");
    const active = root.active; if (!(active instanceof ChatView)) throw Error("missing pane after split");
    active.composer.input.setText("reload must discard this");
    for (const [name, settings] of Object.entries({
      models: { picker: false, effortPicker: false, aliases: false, effortStatus: false },
      controls: { clearAlias: false, exitAliases: false, interrupt: false, navigation: false, panelCommand: false },
      "run-feedback": { tokenSpeed: false, phaseTimers: false, stepTimers: false },
      insights: { status: false, context: false, usage: false },
    })) await fs.writeFile(ctx.root + "/../plugins/" + name + "/settings.json", JSON.stringify(settings));
    ctx.print("MIGRATION_INPUT_PASS", display ? "display" : "logical");
    check(tui.command.available("reload"), true, "native reload exists");
  } catch (error) { ctx.print("MIGRATION_FAIL", String(error)); quit(); } });
}
'''


def terminal(binary, env, work, output, timeout=40):
    pid, fd = pty.fork()
    if pid == 0:
        os.chdir(work)
        os.execve(binary, [str(binary)], env)
    output.with_suffix(".pid").write_text(str(pid))
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", 30, 100, 0, 0))
    captured = bytearray()
    deadline = time.monotonic() + timeout
    status = None
    reload_sent = False
    try:
        while time.monotonic() < deadline:
            if select.select([fd], [], [], 0.05)[0]:
                try:
                    captured.extend(os.read(fd, 65536))
                except OSError as error:
                    if error.errno != errno.EIO:
                        raise
            if not reload_sent:
                logs = "\n".join(path.read_text(errors="replace") for path in Path(env["XDG_STATE_HOME"]).rglob("*.log"))
                if "MIGRATION_INPUT_PASS" in logs:
                    os.write(fd, b"\x07")
                    reload_sent = True
            done, result = os.waitpid(pid, os.WNOHANG)
            if done:
                status = os.waitstatus_to_exitcode(result)
                break
        if status is None:
            os.kill(pid, signal.SIGTERM)
            os.waitpid(pid, 0)
        output.write_bytes(captured)
        return status
    finally:
        os.close(fd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--types-dir", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--cd", action="store_true", help="Check /cd directory-completion integration")
    parser.add_argument("--type-exclude", action="append", default=[], help="Exclude a known baseline type failure; runtime still loads it")
    parser.add_argument("--profile", type=Path, default=Path(__file__).resolve().parents[1] / ".config/yuke")
    args = parser.parse_args()
    binary = args.binary.resolve()
    assert binary.is_file(), "build the candidate first"
    report = args.output.resolve() if args.output else Path(tempfile.mkdtemp(prefix="yuke-manifest-check-"))
    report.mkdir(parents=True, exist_ok=True)
    print("Artifacts:", report, flush=True)
    if args.type_exclude:
        print("Known baseline type exclusions:", args.type_exclude, flush=True)
    for mode in ("logical", "display"):
        root = report / mode
        profile = root / "config/yuke"
        shutil.copytree(args.profile.resolve(strict=True), profile, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "yuke.d.ts", "yuke-modules.d.ts", "yuke.jsconfig.json", "providers.json*", "*.key", ".env"))
        for name in ("home", "cache", "work", "state", "data"):
            (root / name).mkdir()
        (root / "work/folder").mkdir()
        (root / "work/folder/nested.txt").touch()
        if args.cd:
            (root / "work/cd folder").mkdir()
            (root / "work/cd-file.txt").touch()
            (root / "home/home-target").mkdir()
        (profile / "plugins/vim-mode/settings.json").write_text(json.dumps({"verticalMotion": mode}))
        for name in ("yuke.d.ts", "yuke-modules.d.ts"):
            (profile / name).symlink_to((args.types_dir / name).resolve())
        (profile / "yuke.jsconfig.json").write_text(json.dumps({"compilerOptions": {"allowJs": True, "checkJs": True, "noEmit": True, "strict": True, "module": "esnext", "moduleResolution": "bundler", "target": "es2022", "lib": ["es2025"], "types": []}}))
        probe = profile / "probe"
        probe.mkdir()
        (probe / "index.js").write_text(PROBE)
        (probe / "plugin.json").write_text(json.dumps({"name": "migration-probe", "extensions": {"sh.yuke": {"entry": "./index.js", "uses": ["tui", "composer-vim"]}}}))
        config = json.loads((profile / "config.json").read_text())
        config["plugins"].append("./probe")
        (profile / "config.json").write_text(json.dumps(config))
        (profile / "jsconfig.json").write_text(json.dumps({"extends": "./yuke.jsconfig.json", "include": ["types.d.ts", "plugins/**/*.js", "plugins/**/*.d.ts", "probe/*.js", "yuke.d.ts", "yuke-modules.d.ts"], "exclude": ["plugins/**/tests/**", *args.type_exclude]}))
        env = {"PATH": os.environ["PATH"], "HOME": str(root / "home"), "XDG_CACHE_HOME": str(root / "cache"), "XDG_CONFIG_HOME": str(root / "config"), "XDG_DATA_HOME": str(root / "data"), "XDG_STATE_HOME": str(root / "state"), "YUKE_APPNAME": "yuke", "TERM": "xterm-256color", "COLORTERM": "truecolor", "MIGRATION_ROWS": mode}
        if args.cd:
            env["MIGRATION_CD"] = "1"
        for label, command in (("types", ["tsc", "-p", str(profile / "jsconfig.json")]), ("startup", [str(binary), "check"])):
            run = subprocess.run(command, cwd=root / "work", env=env, capture_output=True, timeout=45)
            (root / (label + ".log")).write_bytes(run.stdout + run.stderr)
            assert run.returncode == 0, f"{mode} {label} failed; read {root / (label + '.log')}"
        (probe / "disposed.json").unlink(missing_ok=True)
        status = terminal(binary, env, root / "work", root / "terminal.raw")
        logs = "\n".join(path.read_text(errors="replace") for path in (root / "state").rglob("*.log"))
        (root / "terminal.log").write_text(logs)
        assert status == 0 and "MIGRATION_FAIL" not in logs and "[error]" not in logs, f"{mode} TUI failed; read {root / 'terminal.log'} and terminal.raw"
        if args.cd:
            assert "MIGRATION_CD_COMPLETION_PASS" in logs, "cd completion guard did not finish"
        assert "MIGRATION_INPUT_PASS" in logs and "MIGRATION_RELOAD_PASS" in logs, f"{mode} guard did not finish"
        assert json.loads((probe / "disposed.json").read_text()) == 2, "both runtime generations must release resources"
        run = subprocess.run([str(binary), "--rpc"], input=b'{"id":"initialize-probe","method":"initialize","params":{}}\n', cwd=root / "work", env=env, capture_output=True, timeout=30)
        (root / "headless.log").write_bytes(run.stdout + run.stderr)
        assert run.returncode == 0 and b'"result"' in run.stdout, f"{mode} headless failed"
        print(mode + ": types, startup, input, native reload, disposal, and headless passed", flush=True)
    print("All configured candidate entries passed startup and lifecycle. These guards do not exercise every dialog or external service.")


if __name__ == "__main__":
    main()
