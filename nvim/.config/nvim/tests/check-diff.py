#!/usr/bin/env python3
"""Exercise CodeDiff layout and navigation in an isolated terminal UI."""
import os
from pathlib import Path
import subprocess
import tempfile

from nvim_probe import run_probe

CONFIG = Path(__file__).resolve().parents[1]

PROBE = r'''
local function wait_until(predicate, message)
  local thread = coroutine.running()
  local deadline = vim.uv.now() + 15000
  while not predicate() do
    assert(vim.uv.now() < deadline, message .. "\n" .. vim.v.errmsg)
    vim.defer_fn(function()
      local ok, err = coroutine.resume(thread)
      if not ok then
        vim.fn.writefile({ vim.json.encode({ error = tostring(err) }) }, vim.env.NVIM_TEST_REPORT)
        vim.cmd("cquit 1")
      end
    end, 10)
    coroutine.yield()
  end
end

local function press(keys)
  vim.api.nvim_input(vim.api.nvim_replace_termcodes(keys, true, false, true))
end

vim.cmd.cd(vim.env.NVIM_TEST_PROJECT)
vim.cmd.edit("sample.txt")
local source = vim.api.nvim_get_current_buf()
vim.api.nvim_buf_set_lines(source, 1, 2, false, { "after first (unsaved)" })
press(",jd")
local lifecycle = require("codediff.ui.lifecycle")
wait_until(function()
  local session = lifecycle.get_session(vim.api.nvim_get_current_tabpage())
  return session and session.stored_diff_result
end, "JJ shortcut did not open a rendered diff")
local tab = vim.api.nvim_get_current_tabpage()
local function session() return lifecycle.get_session(tab) end
local function panel() return lifecycle.get_panel_view(tab) end
local function windows()
  local result = {}
  for _, win in ipairs(vim.api.nvim_tabpage_list_wins(tab)) do
    if vim.api.nvim_win_get_config(win).relative == "" then table.insert(result, win) end
  end
  return result
end

assert(lifecycle.get_layout(tab) == "inline", "Wide reviews must start inline")
assert(panel().is_hidden, "Changed-file list must start hidden")
assert(#windows() == 1, "Inline review has extra columns")
assert(vim.api.nvim_win_get_width(windows()[1]) == vim.o.columns, "Diff does not use the full editor width")
assert(vim.api.nvim_get_current_win() == session().modified_win, "Review did not focus the changed code")
wait_until(function() return vim.api.nvim_get_current_line():find("after first", 1, true) end,
  "Review did not jump to the first change")
press("]c")
wait_until(function() return vim.api.nvim_get_current_line() == "after second" end, "Next hunk did not work")
press("[c")
wait_until(function() return vim.api.nvim_get_current_line():find("after first", 1, true) end, "Previous hunk did not work")

press("]f")
wait_until(function() return vim.api.nvim_buf_get_name(session().modified_bufnr):match("extra%.txt$") end,
  "Next file did not work with the file list hidden")
press("[f")
wait_until(function() return session().modified_bufnr == source end,
  "Previous file did not restore the unsaved source buffer")
assert(panel().is_hidden and #windows() == 1, "File navigation showed the hidden list")

press("t")
wait_until(function()
  return lifecycle.get_layout(tab) == "side-by-side" and #windows() == 2
    and session().stored_diff_result and vim.api.nvim_get_current_win() == session().modified_win
    and vim.fn.maparg("t", "n", false, true).callback
end,
  "Layout toggle did not show two code columns")
assert(panel().is_hidden, "Side-by-side toggle showed the file list")
press("t")
wait_until(function()
  return lifecycle.get_layout(tab) == "inline" and #windows() == 1
    and session().stored_diff_result and vim.api.nvim_get_current_win() == session().modified_win
    and vim.fn.maparg("t", "n", false, true).callback
end,
  "Layout toggle did not restore one code column")
press(",b")
wait_until(function() return not panel().is_hidden and #windows() == 2 end, "File list toggle did not show the list")
assert(vim.api.nvim_buf_get_lines(panel().bufnr, 0, -1, false)[1], "Changed-file list is empty")
press(",b")
wait_until(function() return panel().is_hidden and #windows() == 1 end, "File list toggle did not hide the list")
local foldmethod, foldenable = vim.wo.foldmethod, vim.wo.foldenable
press("gc")
wait_until(function() return session().compact_mode and vim.fn.foldclosed(10) ~= -1 end,
  "Unchanged code did not fold")
press("gc")
wait_until(function() return not session().compact_mode end, "Unchanged-code folding did not disable")
assert(vim.wo.foldmethod == foldmethod and vim.wo.foldenable == foldenable, "Folding toggle did not restore window options")

press("q")
wait_until(function() return #vim.api.nvim_list_tabpages() == 1 end, "Review did not close")
assert(vim.bo[source].modified, "Closing review saved or discarded edits")
assert(vim.api.nvim_buf_get_lines(source, 1, 2, false)[1] == "after first (unsaved)")
assert(vim.fn.readfile("sample.txt")[2] == "after first", "Review wrote the source file")
assert(not vim.o.autowrite and not vim.o.autowriteall and vim.o.clipboard == "")
vim.fn.writefile({ vim.json.encode({ inline = true, full_width = true, hidden_list = true,
  toggles = true, file_navigation = true, hunk_navigation = true, folding = true,
  unsaved_edits = true }) }, vim.env.NVIM_TEST_REPORT)
vim.cmd("qa!")
'''

with tempfile.TemporaryDirectory(prefix="nvim-diff-tests-", ignore_cleanup_errors=True) as temporary:
    root = Path(temporary).resolve()
    config_home = root / "config"
    config_home.mkdir()
    (config_home / "nvim").symlink_to(CONFIG, target_is_directory=True)
    project = root / "project with spaces"
    project.mkdir()
    middle = "".join(f"unchanged line {number}\n" for number in range(3, 28))
    source = project / "sample.txt"
    source.write_text("context\nbefore first\n" + middle + "before second\n")
    (project / "extra.txt").write_text("before extra\n")
    for command in (["jj", "git", "init", str(project)], ["jj", "describe", "-m", "Diff fixture baseline"], ["jj", "new"]):
        subprocess.run(command, cwd=project, check=True, capture_output=True, text=True)
    original = "context\nafter first\n" + middle + "after second\n"
    source.write_text(original)
    (project / "extra.txt").write_text("after extra\n")
    environment = dict(os.environ, XDG_CONFIG_HOME=str(config_home), XDG_STATE_HOME=str(root / "state"),
                       XDG_CACHE_HOME=str(root / "cache"), NVIM_TEST_PROJECT=str(project))
    for key in list(environment):
        if key.startswith("HERDR_") or key == "NVIM_APPNAME":
            environment.pop(key)
    result = run_probe(CONFIG, root, environment, PROBE)
    assert source.read_text() == original
    print("Neovim diff checks passed:", result)
