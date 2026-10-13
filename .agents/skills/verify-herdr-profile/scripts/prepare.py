#!/usr/bin/env python3
"""Stage the checked-in Herdr drivers with silent, private test configuration."""
import argparse
from pathlib import Path
import shutil
import tomllib


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path)
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[4] / "herdr/.config/herdr"
    config = (source / "config.toml").read_text()
    settings = tomllib.loads(config)
    if "sound" in settings.get("ui", {}) or "session" in settings:
        parser.error("The source now owns sound or session settings. Reconcile the staging overrides before driving.")
    destination = args.evidence.resolve(strict=True) / "staged-herdr"
    destination.mkdir(mode=0o700)
    shutil.copytree(source / "local-plugins", destination / "local-plugins",
                    ignore=shutil.ignore_patterns("target", "__pycache__", "*.pyc"))
    overrides = "\n[ui.sound]\nenabled = false\n[session]\nresume_agents_on_restore = false\n"
    (destination / "config.toml").write_text(config + overrides)
    guard = destination / "local-plugins/code/tests/check-code-order.py"
    body = guard.read_text()
    fixture_end = "manifest_check = false\\n'"
    if body.count(fixture_end) != 1:
        parser.error("The Code-order fixture configuration changed. Reconcile its silent overrides before driving.")
    guard.write_text(body.replace(fixture_end, "manifest_check = false\\n" + overrides.replace("\n", "\\n") + "'"))
    print(destination)


if __name__ == "__main__":
    main()
