#!/usr/bin/env python3
"""Exercise the Neovim mcat launcher without sending Apple events."""
import os
from pathlib import Path
import tempfile

from nvim_probe import run_probe

CONFIG = Path(__file__).resolve().parents[1]

PROBE = r'''
local function wait_until(predicate, message)
  local thread = coroutine.running()
  local deadline = vim.uv.now() + 5000
  while not predicate() do
    assert(vim.uv.now() < deadline, message)
    vim.defer_fn(function() assert(coroutine.resume(thread)) end, 10)
    coroutine.yield()
  end
end

local completed = 0
local system = vim.system
vim.system = function(args, opts, callback)
  if args[1]:match("/osascript$") then
    return system(args, opts, function(result)
      callback(result)
      vim.schedule(function() completed = completed + 1 end)
    end)
  end
  return system(args, opts, callback)
end
local messages = {}
local function capture(message) messages[#messages + 1] = message end
vim.notify = capture
local function warned(text)
  return #messages > 0 and messages[#messages]:find(text, 1, true) ~= nil
end
local function receipts()
  local lines = vim.fn.readfile(vim.env.NVIM_TEST_RECEIPTS)
  local result = {}
  for _, line in ipairs(lines) do result[#result + 1] = vim.json.decode(line) end
  return result
end
local function press(keys)
  vim.api.nvim_input(vim.api.nvim_replace_termcodes(keys, true, false, true))
end

vim.cmd.edit(vim.env.NVIM_TEST_MARKDOWN)
local buffer = vim.api.nvim_get_current_buf()
local window = vim.api.nvim_get_current_win()
local cwd = vim.fn.getcwd()
assert(vim.fn.exists(":McatPreview") == 2, "McatPreview command is missing")
assert(vim.fn.maparg(",mv", "n", false, true).desc == "Preview Markdown in Ghostty")
assert(vim.fn.maparg(",mp", "n", false, true).desc == "Toggle Markdown rendering")
assert(vim.fn.maparg(",ms", "n", false, true).desc == "Toggle Markdown preview split")
local preview = require("config.markdown_preview")

local path = vim.env.PATH
vim.env.PATH = ""
preview.open()
assert(warned("mcat is missing") and #receipts() == 0)
vim.env.PATH = vim.env.NVIM_TEST_MCAT_ONLY
preview.open()
assert(warned("osascript is missing") and #receipts() == 0)
vim.env.PATH = path

vim.api.nvim_buf_set_lines(buffer, -1, -1, false, { "unsaved" })
preview.open()
assert(warned("Save this file with :w") and #receipts() == 0)
assert(vim.bo[buffer].modified and vim.fn.readfile(vim.env.NVIM_TEST_MARKDOWN)[1] == "# Original")
vim.cmd.write()
local saved = vim.api.nvim_buf_get_lines(buffer, 0, -1, false)
press(",mv")
wait_until(function() return completed == 1 end, "Shortcut did not launch the viewer")
assert(#receipts() == 1)
local launch = receipts()[1]
assert(launch.cwd == vim.fn.fnamemodify(vim.env.NVIM_TEST_MARKDOWN, ":h"), "Viewer has the wrong working directory")
assert(vim.deep_equal(launch.args, { "-I", "--kitty", "--", vim.env.NVIM_TEST_MARKDOWN }),
  "Paths or mcat arguments did not survive the native launch boundary")
assert(vim.deep_equal(launch.content, saved), "Viewer did not receive the saved document")
assert(vim.api.nvim_get_current_buf() == buffer and vim.api.nvim_get_current_win() == window)
assert(vim.fn.getcwd() == cwd and not vim.bo[buffer].modified)

vim.cmd.McatPreview()
wait_until(function() return completed == 2 end, "Command did not launch the viewer")
assert(#receipts() == 2)
vim.notify = capture
preview.open()
preview.open()
assert(warned("already launching"), vim.inspect(messages))
wait_until(function() return completed == 3 end, "Duplicate-launch guard lost the first request")
assert(#receipts() == 3)
vim.fn.writefile({ "fail" }, vim.env.NVIM_TEST_FAILURE)
preview.open()
wait_until(function() return completed == 4 end, "AppleScript launch did not finish")
assert(warned("Automation permission denied"), "AppleScript errors were not reported")
vim.fn.delete(vim.env.NVIM_TEST_FAILURE)
preview.open()
wait_until(function() return completed == 5 end, "Launcher did not recover after an error")
assert(#receipts() == 4)

vim.cmd.enew()
vim.bo.filetype = "markdown"
preview.open()
assert(warned("Open a saved Markdown file") and #receipts() == 4)
vim.cmd.edit(vim.env.NVIM_TEST_NEW_FILE)
preview.open()
assert(warned("Save this file with :w") and #receipts() == 4)
vim.cmd.enew()
vim.bo.filetype = "text"
preview.open()
assert(warned("Open a saved Markdown file") and #receipts() == 4)
assert(vim.fn.maparg(",mv", "n") == "", "Markdown shortcut leaked into a text buffer")
vim.api.nvim_set_current_buf(buffer)
vim.bo.buftype = "nofile"
preview.open()
assert(warned("Open a saved Markdown file") and #receipts() == 4)
vim.bo.buftype = ""
assert(not vim.o.autowrite and not vim.o.autowriteall and vim.o.clipboard == "")
vim.fn.writefile({ vim.json.encode({ passed = true, launches = #receipts() }) }, vim.env.NVIM_TEST_REPORT)
vim.cmd("qa!")
'''

with tempfile.TemporaryDirectory(prefix="nvim-mcat-tests-") as temporary:
    root = Path(temporary).resolve()
    config_home = root / "config"
    config_home.mkdir()
    (config_home / "nvim").symlink_to(CONFIG, target_is_directory=True)
    project = root / "project's notes"
    project.mkdir()
    source = project / "quote' $(touch PWNED); 日本語.md"
    source.write_text("# Original\n\nSaved content\n")
    receipts = root / "receipts.jsonl"
    receipts.touch()
    failure = root / "fail"
    scripts = root / "bin"
    scripts.mkdir()
    mcat = scripts / "mcat"
    mcat.write_text("#!/usr/bin/env python3\nimport json, os, pathlib, sys\n"
                    "record = {'cwd': os.getcwd(), 'args': sys.argv[1:], "
                    "'content': pathlib.Path(sys.argv[-1]).read_text().splitlines()}\n"
                    "with open(os.environ['NVIM_TEST_RECEIPTS'], 'a') as stream: "
                    "stream.write(json.dumps(record) + '\\n')\n")
    osascript = scripts / "osascript"
    osascript.write_text("#!/usr/bin/env python3\nimport os, pathlib, subprocess, sys, time\n"
                         "script = sys.stdin.read()\n"
                         "time.sleep(0.25)\n"
                         "if pathlib.Path(os.environ['NVIM_TEST_FAILURE']).exists():\n"
                         "    sys.stderr.write('Automation permission denied\\n')\n"
                         "    sys.exit(1)\n"
                         "result = subprocess.run(['/bin/sh', '-c', sys.argv[3]], cwd=sys.argv[2])\n"
                         "sys.exit(result.returncode)\n")
    mcat.chmod(0o755)
    osascript.chmod(0o755)
    mcat_only = root / "mcat-only"
    mcat_only.mkdir()
    (mcat_only / "mcat").symlink_to(mcat)
    environment = dict(os.environ, PATH=str(scripts) + os.pathsep + os.environ["PATH"],
                       XDG_CONFIG_HOME=str(config_home), XDG_STATE_HOME=str(root / "state"),
                       XDG_CACHE_HOME=str(root / "cache"), NVIM_TEST_MARKDOWN=str(source),
                       NVIM_TEST_NEW_FILE=str(project / "new.md"), NVIM_TEST_RECEIPTS=str(receipts),
                       NVIM_TEST_FAILURE=str(failure), NVIM_TEST_MCAT_ONLY=str(mcat_only))
    for key in list(environment):
        if key.startswith("HERDR_") or key == "NVIM_APPNAME":
            environment.pop(key)
    result = run_probe(CONFIG, root, environment, PROBE)
    assert result == {"passed": True, "launches": 4}
    assert not (root / "PWNED").exists() and not (project / "PWNED").exists()
    assert source.read_text() == "# Original\n\nSaved content\nunsaved\n"
    print("mcat launcher checks passed: mapping, command, quoting, cwd, save guards, errors, duplicate launch")
