#!/usr/bin/env python3
"""Check the real configuration without desktop or clipboard input.

Requires the pinned plugins to be installed in the normal Neovim data directory.
Editor state, cache, files, and repository fixtures are temporary.
"""
import os
from pathlib import Path
import tempfile

from nvim_probe import run_probe

CONFIG = Path(__file__).resolve().parents[1]

PROBE = r'''
local function wait_until(timeout, predicate)
  local thread = coroutine.running()
  local deadline = vim.uv.now() + timeout
  while not predicate() do
    if vim.uv.now() >= deadline then return false end
    vim.defer_fn(function() assert(coroutine.resume(thread)) end, 10)
    coroutine.yield()
  end
  return true
end

local config = vim.fn.stdpath("config")
for _, path in ipairs(vim.fn.glob(config .. "/lua/**/*.lua", false, true)) do
  local chunk, err = loadfile(path)
  assert(chunk, path .. ": " .. tostring(err))
end
assert(vim.g.mapleader == ",")
assert(vim.o.shiftwidth == 2)
assert(vim.o.expandtab and vim.go.relativenumber)
assert(vim.o.clipboard == "", "Startup must not enable automatic clipboard sync")
assert(not vim.o.autowrite and not vim.o.autowriteall)
assert(vim.go.textwidth == 99 and vim.go.colorcolumn == "100")
assert(vim.o.undolevels == 10000)
assert(vim.fn.maparg("j", "n") == "gj")
assert(vim.fn.maparg("k", "n") == "gk")
assert(vim.fn.exists(":VimShortcuts") == 2)
for _, key in ipairs({ ",<space>", ",ff", ",/", ",sg", ",tt", ",tg" }) do
  local mapping = vim.fn.maparg(key, "n", false, true)
  local expected = (key == ",/" or key == ",sg" or key == ",tg") and "Search project" or "Find files"
  assert(mapping.desc == expected, "Missing picker mapping: " .. key)
end
assert(vim.fn.maparg(",<Esc>", "n") == "<Cmd>nohlsearch<CR>")
vim.api.nvim_input(":")
assert(wait_until(3000, function()
  local trigger = package.loaded["blink.cmp.completion.trigger"]
  return vim.api.nvim_get_mode().mode == "c" and trigger and trigger.cmdline_events ~= nil
end), "Command-line completion did not load before entering insert mode")
vim.api.nvim_input("VimShort")
local cmp = require("blink.cmp")
assert(wait_until(3000, function()
  if not cmp.is_menu_visible() then return false end
  for _, item in ipairs(cmp.get_items()) do
    if item.label == "VimShortcuts" then return true end
  end
  return false
end), "Command-line completion did not automatically offer VimShortcuts")
assert(vim.fn.getcmdline() == "VimShort", "Completion changed the command before selection")
vim.api.nvim_input("<Tab>")
assert(wait_until(3000, function() return vim.fn.getcmdline() == "VimShortcuts" end),
  "Tab did not complete the command")
assert(vim.api.nvim_get_mode().mode == "c", "Completing the command executed it")
vim.api.nvim_input("<Esc>")
assert(wait_until(3000, function() return vim.api.nvim_get_mode().mode == "n" end),
  "Escape did not cancel the command")
assert(vim.fn.bufnr("Vim shortcuts") == -1, "Canceling completion executed the command")
vim.api.nvim_input(":edit " .. vim.env.NVIM_TEST_PROJECT .. "/nested/fi")
assert(wait_until(3000, function()
  if not cmp.is_menu_visible() then return false end
  for _, item in ipairs(cmp.get_items()) do
    if item.label == "fixture.txt" then return true end
  end
  return false
end), "Command-line completion did not offer the fixture path")
vim.api.nvim_input("<Tab>")
assert(wait_until(3000, function() return vim.fn.getcmdline() == "edit " .. vim.env.NVIM_TEST_FILE end),
  "Tab did not complete the file path")
vim.api.nvim_input("<Esc>")
assert(wait_until(3000, function() return vim.api.nvim_get_mode().mode == "n" end))
assert(vim.api.nvim_buf_get_name(0) ~= vim.env.NVIM_TEST_FILE, "Canceling path completion opened the file")
local lazy = require("lazy")
lazy.load({ plugins = { "jj.nvim", "codediff.nvim", "herdr-nvim" } })
assert(type(require("config.herdr_review").setup) == "function")
assert(type(require("herdr-nvim.ask").set_target) == "function")
assert(type(require("codediff.config").options) == "table")
local projects = require("config.projects")
local original_cwd = vim.fn.getcwd()
vim.cmd.edit(vim.env.NVIM_TEST_FILE)
assert(vim.o.expandtab and vim.o.relativenumber and vim.o.textwidth == 99 and vim.o.colorcolumn == "100")
assert(projects.root() == vim.env.NVIM_TEST_PROJECT)
assert(vim.fn.getcwd() == original_cwd, "Root lookup changed the working directory")
local tree = require("nvim-tree.api")
vim.api.nvim_feedkeys(",E", "xt", false)
assert(wait_until(3000, function() return vim.bo.filetype == "NvimTree" end), ",E did not reveal and focus the file tree")
assert(tree.tree.get_node_under_cursor().absolute_path == vim.env.NVIM_TEST_FILE, ",E highlighted the wrong file")
vim.cmd.wincmd("p")
assert(vim.api.nvim_buf_get_name(0) == vim.env.NVIM_TEST_FILE)
vim.api.nvim_feedkeys(",E", "xt", false)
assert(wait_until(3000, function() return vim.bo.filetype == "NvimTree" end), ",E toggled an open tree closed")
assert(tree.tree.get_node_under_cursor().absolute_path == vim.env.NVIM_TEST_FILE)
vim.api.nvim_feedkeys(",e", "xt", false)
assert(wait_until(3000, function() return not tree.tree.is_visible() end), ",e no longer closes the file tree")
assert(vim.api.nvim_buf_get_name(0) == vim.env.NVIM_TEST_FILE)
assert(vim.fn.getcwd() == original_cwd, "Tree reveal changed the working directory")
vim.api.nvim_input("/original")
assert(wait_until(3000, function()
  local context = cmp.get_context()
  return context and context.line == "original" and #cmp.get_items() > 0
end), "Search completion did not process the buffer words")
assert(not cmp.is_menu_visible(), "Search input unexpectedly opened an automatic completion menu")
assert(vim.fn.getcmdline() == "original", "Search completion changed the search text")
vim.api.nvim_input("<Esc>")
assert(wait_until(3000, function() return vim.api.nvim_get_mode().mode == "n" end))
for _, key in ipairs({ ",<space>", ",ff", ",tt", ",/", ",sg", ",tg" }) do
  local grep = key == ",/" or key == ",sg" or key == ",tg"
  vim.api.nvim_win_set_cursor(0, { 2, 0 })
  vim.api.nvim_feedkeys(vim.api.nvim_replace_termcodes(key, true, false, true), "xt", false)
  assert(wait_until(3000, function() return vim.bo.filetype == "fzf" end), "Picker did not open: " .. key)
  local picker_buffer = vim.api.nvim_get_current_buf()
  local channel = vim.bo.channel
  assert(wait_until(3000, function()
    local lines = table.concat(vim.api.nvim_buf_get_lines(picker_buffer, 0, -1, false), "\n")
    return lines:find("%d+/%d+") ~= nil
  end), "Picker prompt did not become ready: " .. key .. "\n" ..
    table.concat(vim.api.nvim_buf_get_lines(picker_buffer, 0, -1, false), "\n"))
  vim.api.nvim_chan_send(channel, grep and "original fixture" or "fixture")
  assert(wait_until(5000, function()
    local lines = table.concat(vim.api.nvim_buf_get_lines(picker_buffer, 0, -1, false), "\n")
    return lines:find("fixture.txt", 1, true) ~= nil
  end), "Picker did not find the project fixture: " .. key .. "\n" ..
    table.concat(vim.api.nvim_buf_get_lines(picker_buffer, 0, -1, false), "\n"))
  vim.api.nvim_chan_send(channel, "\r")
  assert(wait_until(3000, function() return vim.api.nvim_get_current_buf() ~= picker_buffer end),
    "Picker did not accept the result: " .. key)
  assert(vim.api.nvim_buf_get_name(0) == vim.env.NVIM_TEST_FILE, "Picker opened the wrong file: " .. key)
  if grep then
    assert(vim.api.nvim_win_get_cursor(0)[1] == 1, "Grep did not jump to the matching line: " .. key)
  end
  assert(vim.fn.getcwd() == original_cwd, "Picker changed the working directory: " .. key)
end
vim.fn.setreg("/", "original fixture")
vim.v.hlsearch = 1
vim.api.nvim_feedkeys(vim.api.nvim_replace_termcodes(",<Esc>", true, false, true), "xt", false)
assert(vim.v.hlsearch == 0, "Clear-highlights shortcut did not clear the search")
vim.api.nvim_buf_set_lines(0, 0, -1, false, { "unsaved fixture" })
local file_buffer = vim.api.nvim_get_current_buf()
require("config.shortcuts").open()
assert(vim.fn.fnamemodify(vim.api.nvim_buf_get_name(0), ":t") == "Vim shortcuts")
assert(vim.bo.readonly and not vim.bo.modifiable)
assert(table.concat(vim.api.nvim_buf_get_lines(0, 0, -1, false), "\n"):find("Herdr"))
vim.api.nvim_feedkeys("q", "xt", false)
assert(vim.api.nvim_get_current_buf() == file_buffer)
assert(vim.bo.modified, "Closing the guide lost the unsaved file")
assert(vim.fn.readfile(vim.env.NVIM_TEST_FILE)[1] == "original fixture")
vim.fn.writefile({ vim.json.encode({ config = true, completion = true, pickers = true, tree_reveal = true, unsaved_edits = true }) }, vim.env.NVIM_TEST_REPORT)
vim.cmd("qa!")
'''

with tempfile.TemporaryDirectory(prefix="nvim-config-tests-") as temporary:
    root = Path(temporary).resolve()
    config_home = root / "config"
    config_home.mkdir()
    (config_home / "nvim").symlink_to(CONFIG, target_is_directory=True)
    project = root / "project"
    (project / ".jj").mkdir(parents=True)
    source = project / "nested" / "fixture.txt"
    source.parent.mkdir()
    source.write_text("original fixture\nunmatched second line\n")
    environment = dict(os.environ, XDG_CONFIG_HOME=str(config_home),
                       XDG_STATE_HOME=str(root / "state"), XDG_CACHE_HOME=str(root / "cache"),
                       NVIM_TEST_FILE=str(source), NVIM_TEST_PROJECT=str(project))
    for key in list(environment):
        if key.startswith("HERDR_") or key == "NVIM_APPNAME":
            environment.pop(key)
    result = run_probe(CONFIG, root, environment, PROBE)
    print("Neovim config checks passed:", result)
    assert source.read_text() == "original fixture\nunmatched second line\n"
