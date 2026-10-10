#!/usr/bin/env python3
"""Check that the bottom bar identifies the running engine, not Yuke on PATH."""
import json
import pathlib
import shutil
import subprocess
import tempfile
import time
import uuid

TMUX = shutil.which("tmux")
YUKE = shutil.which("yuke")
assert TMUX and YUKE, "tmux and yuke are required"
plugin = pathlib.Path(__file__).resolve().parents[1] / "plugins" / "build-status.js"
expected = subprocess.check_output([YUKE, "--version"], text=True).strip()
socket = "yuke-build-" + uuid.uuid4().hex[:10]
transcript = []


def tmux(*args, check=True):
    return subprocess.run([TMUX, "-L", socket, *args], check=check, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)


try:
    with tempfile.TemporaryDirectory(prefix="yuke-build-") as directory:
        root = pathlib.Path(directory)
        profile = root / "config" / "yuke"
        profile.mkdir(parents=True)
        (profile / "index.js").write_text(
            'import { plugins } from "yuke";\n'
            f'import {{ buildStatus }} from {json.dumps(str(plugin))};\n'
            'plugins.use(buildStatus);\n'
        )
        # A replaced binary or a different PATH must not mislabel an old process.
        fake_bin = root / "bin"
        fake_bin.mkdir()
        fake_yuke = fake_bin / "yuke"
        fake_yuke.write_text('#!/bin/sh\necho "yuke WRONG-ON-DISK"\n')
        fake_yuke.chmod(0o700)
        run = root / "run.sh"
        run.write_text(
            "#!/bin/sh\n"
            f"export XDG_CONFIG_HOME={json.dumps(str(root / 'config'))}\n"
            f"export XDG_DATA_HOME={json.dumps(str(root / 'data'))}\n"
            f"export XDG_STATE_HOME={json.dumps(str(root / 'state'))}\n"
            f"export XDG_CACHE_HOME={json.dumps(str(root / 'cache'))}\n"
            "unset HERDR_ENV HERDR_PANE_ID HERDR_SOCKET_PATH\n"
            "export TERM=xterm-256color\n"
            f"export PATH={json.dumps(str(fake_bin))}\n"
            f"exec {json.dumps(YUKE)}\n"
        )
        run.chmod(0o700)
        tmux("new-session", "-d", "-x", "160", "-y", "24", "-s", "test", str(run))
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            screen = tmux("capture-pane", "-t", "test", "-p").stdout
            if expected in screen:
                assert "WRONG-ON-DISK" not in screen
                transcript.append("=== running build in bottom bar ===\n" + screen)
                break
            time.sleep(0.05)
        else:
            raise AssertionError(f"missing running build {expected!r}\n{screen}")
        assert expected in screen.splitlines()[-1], "the build label was not in the bottom bar"
finally:
    tmux("kill-server", check=False)
    with tempfile.NamedTemporaryFile(prefix="yuke-build-", suffix=".txt", mode="w", delete=False) as artifact:
        artifact.write("\n".join(transcript))
        print("Saved build status transcript:", artifact.name)

print("Build status tmux check passed:", expected)
