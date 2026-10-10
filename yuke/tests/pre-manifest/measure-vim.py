#!/usr/bin/env python3
"""Compare profile input and cached composer drawing in isolated QuickJS hosts. Do not use desktop input."""
import argparse
import json
import fcntl
import pty
import select
import struct
import termios
import time
import os
from pathlib import Path
import statistics
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--base", type=Path, required=True, help="saved baseline plugins directory")
parser.add_argument("--runs", type=int, default=6)
parser.add_argument("--iterations", type=int, default=30000)
args = parser.parse_args()
head = Path(__file__).resolve().parents[1] / "plugins"
source = r'''
import { plugins } from "yuke";
import { client } from "yuke";
import { quit } from "yuke:ui";
import { vimImproved } from PLUGIN;
plugins.use(vimImproved);
plugins.use({ name: "vim-cost", apply(ctx) {
 ctx.inject(["tui", "composer-vim"], c => {
  const view = c.tui.root.active, composer = view.composer, input = composer.input, mode = c["composer-vim"];
  composer.layout({x: 0, y: 0, w: 80, h: 6});
  const fixture = "alpha bravo charlie delta\none two three";
  function ev(char, code = "char") { return {type: "key", code, char, text: char, event: "press", mods: 0, shifted: "", baseLayout: ""}; }
  const w = ev("w"), b = ev("b"), x = ev("x"), backspace = ev("", "backspace"), d = ev("d"), v = ev("v"), l = ev("l"), esc = ev("", "esc"), i = ev("i");
  function reset() { mode.setMode(composer, "insert"); input.setText(fixture); input.caret = 0; mode.setMode(composer, "normal"); }
  function motion() { c.tui.root.onEvent(w); c.tui.root.onEvent(b); }
  function typing() { c.tui.root.onEvent(x); c.tui.root.onEvent(backspace); }
  function edit() { input.setText(fixture); input.caret = 0; c.tui.root.onEvent(d); c.tui.root.onEvent(w); c.tui.root.onEvent(i); c.tui.root.onEvent(x); c.tui.root.onEvent(esc); }
  function draw() { composer.draw(true); }
  function measure(name, step) {
   for (let n = 0; n < 2000; n++) step();
   const before = client.memoryUsage(), start = Date.now();
   for (let n = 0; n < ITERATIONS; n++) step();
   const ms = Date.now() - start, after = client.memoryUsage();
   c.print("RESULT " + JSON.stringify({name, ms, heapDelta: after.heap - before.heap, objectDelta: after.objectCount - before.objectCount, arrayDelta: after.arrayCount - before.arrayCount}));
  }
  setTimeout(() => {
  reset(); measure("motion", motion);
  reset(); mode.setMode(composer, "insert"); measure("typing", typing);
  mode.setMode(composer, "normal"); measure("edit", edit);
  reset(); measure("draw", draw);
  c.tui.root.onEvent(v); c.tui.root.onEvent(l); c.tui.root.onEvent(l); measure("visual_draw", draw);
  setTimeout(() => quit(), 20);
  }, 100);
 });
}});
'''
results = {"base": {}, "head": {}}
with tempfile.TemporaryDirectory(prefix="yuke-vim-cost-") as directory:
    tmp = Path(directory)
    for run in range(args.runs):
        order = ["base", "head"] if run % 2 == 0 else ["head", "base"]
        for side in order:
            root = tmp / f"{side}-{run}"
            profile = root / "yuke"
            profile.mkdir(parents=True)
            plugin = (args.base if side == "base" else head) / "vim-improved.js"
            (profile / "index.js").write_text(source.replace("PLUGIN", json.dumps(str(plugin))).replace("ITERATIONS", str(args.iterations)))
            env = os.environ.copy()
            env.update(XDG_CONFIG_HOME=str(root), XDG_DATA_HOME=str(root / "data"), XDG_STATE_HOME=str(root / "state"), YUKE_APPNAME="yuke")
            master, slave = pty.openpty()
            fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 80, 0, 0))
            process = subprocess.Popen(["yuke"], stdin=slave, stdout=slave, stderr=slave, env=env)
            os.close(slave)
            output = bytearray()
            try:
                deadline = time.monotonic() + 180
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
                if code:
                    raise RuntimeError(f"yuke exited with {code}: " + output.decode(errors="replace"))
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
                os.close(master)
            logs = "\n".join(path.read_text(errors="replace") for path in (root / "state").rglob("*.log"))
            for line in logs.splitlines():
                if "RESULT " not in line:
                    continue
                result = json.loads(line.split("RESULT ", 1)[1])
                results[side].setdefault(result["name"], []).append(result)
            if len([line for line in logs.splitlines() if "RESULT " in line]) != 5:
                raise RuntimeError("benchmark did not finish: " + logs + output.decode(errors="replace"))
            print(f"{side} run {run + 1} done", flush=True)


def lower_quartile(items):
    values = sorted(item["ms"] for item in items)
    return statistics.mean(values[:max(1, len(values) // 4)])


for name, base in results["base"].items():
    head_results = results["head"][name]
    assert len(base) == len(head_results) == args.runs
    base_ms, head_ms = lower_quartile(base), lower_quartile(head_results)
    delta = (head_ms / base_ms - 1) * 100 if base_ms else 0
    print(f"{name:12} base={base_ms:7.1f}ms head={head_ms:7.1f}ms delta={delta:+6.1f}%")
    print("  heap deltas (bytes): base", [item["heapDelta"] for item in base], "head", [item["heapDelta"] for item in head_results])
artifact = Path(tempfile.gettempdir()) / "yuke-vim-parity-cost.json"
artifact.write_text(json.dumps({"iterations": args.iterations, "runs": args.runs, "results": results}, indent=2))
print("Saved:", artifact)
print("Wall time has about 20% noise. Heap deltas include GC timing. This check does not count allocations or instructions.")
