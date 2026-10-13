#!/usr/bin/env python3
"""Check compact build labels in private terminals without changing engine identity."""
import argparse
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tempfile
import time
import uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--profile", type=Path, default=Path(__file__).resolve().parents[1] / ".config/yuke")
    args = parser.parse_args()
    binary = args.binary.resolve(strict=True)
    tmux = shutil.which("tmux")
    assert tmux, "tmux is required"
    version = subprocess.check_output([str(binary), "--version"], text=True).strip().removeprefix("yuke ")
    match = re.fullmatch(r"(.+)\+([0-9a-f]{8})[0-9a-f]*(\.dirty)?\.b\d{14}", version)
    assert match, "Use a timestamped local install to exercise compact rendering"
    compact = match[1] + "+" + match[2] + (match[3] or "")
    assert compact != version
    root = Path(tempfile.mkdtemp(prefix="yuke-build-label-")).resolve()
    root.chmod(0o700)
    print("Artifacts:", root, flush=True)
    source = args.profile.resolve(strict=True) / "plugins"
    profile = root / "config/yuke"
    for name in ("build-status", "status"):
        shutil.copytree(source / name, profile / name)
    probe = profile / "probe"
    probe.mkdir()
    (probe / "plugin.json").write_text(json.dumps({"name": "build-label-probe", "extensions": {"sh.yuke": {"entry": "./index.js", "uses": ["tui"]}}}))
    (probe / "index.js").write_text('''
import { env, fs } from "yuke";
import { ChatView } from "yuke:chat";
import { quit } from "yuke:ui";
export default function(ctx) {
  const tui = ctx.get("tui");
  if (!tui) return;
  tui.keymap.add({ "ctrl+s": () => tui.command.perform("status:show"), "ctrl+g": "reload", "ctrl+q": () => quit() });
  ctx.once("ui.started", async () => {
    const pane = tui.root.active;
    if (pane instanceof ChatView) pane.composer.input.setText("UNSENT_BUILD_DRAFT");
    const marker = env.get("BUILD_GENERATION");
    const count = await fs.stat(marker) ? JSON.parse(await fs.readFile(marker)) : 0;
    await fs.writeFile(marker, JSON.stringify(count + 1));
  });
}
''')
    (profile / "config.json").write_text(json.dumps({"plugins": ["./build-status", "./status", "./probe"]}))
    for name in ("home", "work", "data", "state", "cache", "bin"):
        (root / name).mkdir()
    fake = root / "bin/yuke"
    fake.write_text('#!/bin/sh\necho "yuke WRONG-ON-DISK"\n')
    fake.chmod(0o700)
    env = {"PATH": str(root / "bin") + os.pathsep + os.environ["PATH"], "HOME": str(root / "home"), "TERM": "xterm-256color", "YUKE_APPNAME": "yuke", "BUILD_GENERATION": str(root / "generation.json")}
    for name in ("config", "data", "state", "cache"):
        env["XDG_" + name.upper() + "_HOME"] = str(root / name)
    socket = "yuke-build-label-" + uuid.uuid4().hex[:10]
    captures = []

    def mux(*argv, check=True):
        result = subprocess.run([tmux, "-L", socket, *argv], capture_output=True, text=True, check=check, timeout=10)
        return result.stdout

    def screen():
        return mux("capture-pane", "-p", "-t", "build")

    def wait(condition, label):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if condition():
                captures.append(label + "\n" + screen())
                return
            time.sleep(0.05)
        raise AssertionError(label + "\n" + screen())

    def check_labels():
        display = screen()
        assert version not in display, "The UI still shows the full timestamped build"
        assert "WRONG-ON-DISK" not in display, "The label came from the executable on PATH"
        assert "yuke " + compact in display.splitlines()[-1], "The bottom bar lost its compact build label"

    try:
        command = shlex.join(["env", "-i", *(f"{key}={value}" for key, value in env.items()), str(binary)])
        mux("new-session", "-d", "-x", "160", "-y", "55", "-s", "build", "-n", "Agent Tests build label", "-c", str(root / "work"), command)
        wait(lambda: "UNSENT_BUILD_DRAFT" in screen(), "private UI started")
        wait(lambda: "yuke " + compact in screen(), "bottom bar has the compact build label")
        check_labels()
        mux("send-keys", "-t", "build", "C-s")
        wait(lambda: "Account allowance" in screen(), "status dialog opened")
        wait(lambda: "Refreshing..." not in screen() and "Reading allowance..." not in screen(), "status read finished")
        mux("send-keys", "-t", "build", "d")
        wait(lambda: any(re.search(r"\bBuild\s+" + re.escape(compact) + r"\b", line) for line in screen().splitlines()), "status Build row has the compact label")
        check_labels()
        mux("send-keys", "-t", "build", "Escape")
        wait(lambda: "Account allowance" not in screen() and "UNSENT_BUILD_DRAFT" in screen(), "closing status preserves the draft")
        mux("send-keys", "-t", "build", "C-g")
        wait(lambda: (root / "generation.json").exists() and json.loads((root / "generation.json").read_text()) == 2, "native reload completed")
        wait(lambda: "yuke " + compact in screen(), "compact build label returns after reload")
        check_labels()
        rpc = subprocess.run([str(binary), "--rpc"], input='{"id":"build-label","method":"initialize","params":{}}\n', env=env, cwd=root / "work", capture_output=True, text=True, check=True, timeout=20)
        (root / "initialize.jsonl").write_text(rpc.stdout)
        reply = next(json.loads(line) for line in rpc.stdout.splitlines() if json.loads(line).get("id") == "build-label")
        assert reply["result"]["engine"]["version"] == version, "UI formatting changed RPC version identity"
        assert subprocess.check_output([str(binary), "--version"], text=True).strip() == "yuke " + version
        mux("send-keys", "-t", "build", "C-q")
        print("PASS: bottom bar, status details, reload, draft preservation, PATH independence, and full CLI/RPC identity")
    finally:
        mux("kill-server", check=False)
        (root / "screens.txt").write_text("\n\n".join(captures))


if __name__ == "__main__":
    main()
