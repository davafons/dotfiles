#!/usr/bin/env python3
"""Check the Rust profile against the exact source declarations of its Yuke checkout."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--source", type=Path, required=True)
args = parser.parse_args()
source = args.source.resolve(strict=True)
profile = Path(__file__).resolve().parents[1]
config = json.loads((source / "crates/js/tsconfig.json").read_text())
config["compilerOptions"]["paths"] = {"yuke:*": [str(source / "crates/js/modules/*.ts")]}
config["compilerOptions"]["allowJs"] = True
config["compilerOptions"]["checkJs"] = True
config["include"] = [str(source / "crates/js/types/**/*.d.ts")]
config["files"] = [str(path) for path in profile.rglob("*.ts")]
with tempfile.TemporaryDirectory(prefix="yuke-rust-types-") as directory:
    path = Path(directory) / "tsconfig.json"
    path.write_text(json.dumps(config))
    subprocess.run(["mise", "exec", "--", "tsc", "-p", str(path)], cwd=source, check=True)
