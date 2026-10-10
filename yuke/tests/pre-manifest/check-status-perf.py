#!/usr/bin/env python3
"""Compare the unused /status plugin with no plugin on real QuickJS TUI workloads."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--repo", type=Path, required=True)
parser.add_argument("--phase", choices=["all", "frame", "stream", "input"], default="all")
parser.add_argument("--time-only", action="store_true")
parser.add_argument("--iterations", type=int, default=3000)
parser.add_argument("--runs", type=int, default=5)
args = parser.parse_args()
if args.iterations <= 0 or args.runs < 5:
    parser.error("Use positive iterations and at least five runs")
repo = args.repo.resolve()
profile = Path(__file__).resolve().parents[1]
root = Path(tempfile.mkdtemp(prefix="yuke-status-bench-"))
print("REPORT_ROOT", root, flush=True)
plugin = profile / "plugins/status.js"
(root / "status.js").write_bytes(plugin.read_bytes())
(root / "manifest.json").write_text(json.dumps({
    "plugin_sha256": hashlib.sha256(plugin.read_bytes()).hexdigest(), "repo": str(repo),
    "chat_sha256": hashlib.sha256((repo / "src/js/bench/chat.js").read_bytes()).hexdigest(),
    "base": "composerVim, without status", "head": "composerVim, with status; never opened",
    "time": f"{args.runs} alternating runs, lowest quartile; {args.iterations} iterations",
    "phase": args.phase, "time_only": args.time_only,
    "metrics": "separate build; slopes 1500-3000 and 4500-6000",
}, indent=2))
cache = root / "cache"
try:
    for side in ("base", "head"):
        dest = root / side
        dest.mkdir()
        for name in ("src", "lib", "schema", "bench", "tools"):
            shutil.copytree(repo / name, dest / name, ignore=shutil.ignore_patterns("__pycache__"))
        for name in ("build.zig", "build.zig.zon"):
            shutil.copy2(repo / name, dest / name)
        path = dest / "src/js/bench/chat.js"
        source = path.read_text()
        source = 'import { composerVim } from "yuke:plugins";\n' + (
            'import { status } from ' + json.dumps(str(root / "status.js")) + ';\n' if side == "head" else "") + source
        source = source.replace("plugins.use(tuiPlugin);", "plugins.use(tuiPlugin);\nplugins.use(composerVim);" + ("\nplugins.use(status);" if side == "head" else ""))
        source = source.replace("  digest.session = globalThis.PROJECTION_SESSION;", "  digest.session = globalThis.PROJECTION_SESSION;\n  events.emit(\"session.current.changed\");\n  setInputMode(root.active.composer, \"insert\");")
        source = source.replace("else root.invalidate();", "else { if (globalThis.STATUS_INPUT) { root.onEvent(inputKey); root.onEvent(eraseKey); } root.invalidate(); }")
        source = source.replace("const DRAFT_ID = 2;", '''let setInputMode;
plugins.use({ name: "bench-input-mode", apply(ctx) { ctx.inject(["composer-vim"], c => { setInputMode = c["composer-vim"].setMode; }); } });
const inputKey = { type: "key", code: "char", char: "x", shifted: "X", baseLayout: "x", text: "x", event: "press", mods: 0 };
const eraseKey = { type: "key", code: "backspace", char: "", shifted: "", baseLayout: "", text: "", event: "press", mods: 0 };
const DRAFT_ID = 2;''')
        path.write_text(source)

    def build(side, metrics=False):
        subprocess.run(["zig", "build", "bench-install", "-Doptimize=ReleaseFast", "--cache-dir", str(cache)] +
                       (["-Dmetrics=true"] if metrics else []), cwd=root / side, check=True)

    def input_mode(value):
        for side in ("base", "head"):
            path = root / side / "src/js/bench/chat.js"
            source = path.read_text().replace("globalThis.STATUS_INPUT = true;\n", "").replace("globalThis.STATUS_INPUT = false;\n", "")
            path.write_text("globalThis.STATUS_INPUT = " + ("true" if value else "false") + ";\n" + source)

    def run(side, phase, count):
        result = subprocess.run([str(root / side / "zig-out/bin/yuke-bench"), "--fixture", str(repo / "bench/transcript-fixture.json"),
                                 "--phase", phase, "--iterations", str(count)], capture_output=True, text=True, check=True)
        return [dict(json.loads(line), side=side) for line in result.stdout.splitlines()]

    summary = {}
    input_mode(args.phase == "input")
    for side in ("base", "head"):
        build(side)
    with (root / "time.jsonl").open("w") as out:
        for workload, phase in (("frame", "chat_frame"), ("stream", "chat_stream"), ("input", "chat_frame")):
            if args.phase != "all" and args.phase != workload:
                continue
            if workload == "input" and args.phase == "all":
                input_mode(True)
                for side in ("base", "head"):
                    build(side)
            samples = {"base": [], "head": []}
            for repeat in range(args.runs):
                for side in (("base", "head") if repeat % 2 == 0 else ("head", "base")):
                    for row in run(side, phase, args.iterations):
                        row.update(workload=workload, run=repeat)
                        out.write(json.dumps(row) + "\n")
                        out.flush()
                        samples[side].append(row["median_ns"])
            quartiles = {side: sum(sorted(values)[:len(values) // 4]) / (len(values) // 4) for side, values in samples.items()}
            summary[workload] = {"lowest_quartile_ns": quartiles, "delta_percent": 100 * (quartiles["head"] / quartiles["base"] - 1)}
            print(workload, summary[workload], flush=True)
    if not args.time_only:
        with (root / "metrics.jsonl").open("w") as out:
            for side in ("base", "head"):
                build(side, True)
            for workload, phase in (("input", "chat_frame"), ("frame", "chat_frame"), ("stream", "chat_stream")):
                if args.phase != "all" and args.phase != workload:
                    continue
                if workload == "frame":
                    input_mode(False)
                    for side in ("base", "head"):
                        build(side, True)
                rows = {}
                for count in (1500, 3000, 4500, 6000):
                    for side in ("base", "head"):
                        values = run(side, phase, count)
                        rows[count, side] = values[0]
                        for row in values:
                            row["workload"] = workload
                            out.write(json.dumps(row) + "\n")
                            out.flush()
                slopes = []
                for lo, hi in ((1500, 3000), (4500, 6000)):
                    for side in ("base", "head"):
                        a, b = rows[lo, side], rows[hi, side]
                        slopes.append({"side": side, "window": [lo, hi],
                            "allocs_per_iteration": (b["allocations"]["allocations"] - a["allocations"]["allocations"]) / (hi - lo),
                            "allocated_bytes_per_iteration": (b["allocations"]["allocated_bytes"] - a["allocations"]["allocated_bytes"]) / (hi - lo)})
                summary[workload]["metrics"] = slopes
                summary[workload]["live_memory_delta_bytes"] = rows[6000, "head"]["backing_live_bytes"] - rows[6000, "base"]["backing_live_bytes"]
                print(workload, "metrics", slopes, flush=True)
    (root / "summary.json").write_text(json.dumps(summary, indent=2))
finally:
    for name in ("base", "head", "cache"):
        shutil.rmtree(root / name, ignore_errors=True)
    print("Retained reports:", root, flush=True)
