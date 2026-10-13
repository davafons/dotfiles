"""Run a Neovim probe in an isolated terminal and require an explicit result."""
import errno
import fcntl
import json
import os
from pathlib import Path
import pty
import select
import shutil
import struct
import subprocess
import termios
import tempfile
import time


def run_probe(config, root, environment, probe, timeout=90):
    nvim = shutil.which("nvim")
    assert nvim, "Neovim is required"
    probe_path = root / "probe.lua"
    probe_path.write_text(probe)
    report = root / "report.json"
    environment = dict(environment, TERM="xterm-256color", NVIM_TEST_REPORT=str(report))
    command = "lua vim.api.nvim_create_autocmd('VimEnter', {once=true, callback=function() vim.schedule(function() " \
              "coroutine.wrap(function() local ok, err = pcall(assert(loadfile(" + json.dumps(str(probe_path)) + "))); " \
              "if not ok then vim.fn.writefile({vim.json.encode({error=tostring(err)})}, " + json.dumps(str(report)) + "); " \
              "vim.cmd('cquit 1') end end)() end) end})"
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 50, 160, 0, 0))
    process = subprocess.Popen([nvim, "-n", "-i", "NONE", "-u", str(config / "init.lua"), "-c", command],
                               stdin=slave, stdout=slave, stderr=slave, env=environment, cwd=root)
    os.close(slave)
    output = bytearray()
    deadline = time.monotonic() + timeout
    try:
        while process.poll() is None:
            if time.monotonic() >= deadline:
                raise TimeoutError("Neovim probe timed out")
            if select.select([master], [], [], 0.1)[0]:
                try:
                    output.extend(os.read(master, 65536))
                except OSError as error:
                    if error.errno != errno.EIO:
                        raise
                    break
        process.wait(timeout=5)
    except Exception:
        artifact = Path(tempfile.gettempdir()) / "nvim-probe-terminal.log"
        artifact.write_bytes(output)
        print(f"Terminal output saved to {artifact}")
        raise
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        os.close(master)
    if not report.exists():
        raise AssertionError(f"Neovim exited with {process.returncode} before completing the probe")
    result = json.loads(report.read_text())
    assert not result.get("error"), result.get("error")
    assert process.returncode == 0, f"Neovim exited with {process.returncode}"
    return result

