#!/usr/bin/env python3
"""Exercise editor enhancements in an isolated, invisible terminal UI."""
import os
from pathlib import Path
import tempfile

from nvim_probe import run_probe

CONFIG = Path(__file__).resolve().parents[1]

PROBE = r'''
local function wait_until(predicate, message)
  local thread = coroutine.running()
  local deadline = vim.uv.now() + 15000
  while not predicate() do
    assert(vim.uv.now() < deadline, message)
    vim.defer_fn(function() assert(coroutine.resume(thread)) end, 10)
    coroutine.yield()
  end
end

local function press(keys)
  vim.api.nvim_input(vim.api.nvim_replace_termcodes(keys, true, false, true))
end

assert(#vim.api.nvim_list_uis() > 0, "This check requires a terminal UI")
wait_until(function()
  return package.loaded["noice.config"] and require("noice.config").is_running()
end, "Noice did not start automatically")
vim.cmd.edit(vim.env.NVIM_TEST_BIGFILE)
local big = vim.api.nvim_get_current_buf()
assert(vim.bo[big].filetype == "bigfile", "Large Lua file was not classified as bigfile")
assert(vim.b[big].completion == false, "Large file did not disable completion")
assert(vim.wo.foldmethod == "manual", "Large file enabled expensive folding")
assert(not vim.treesitter.highlighter.active[big], "Large file enabled Treesitter highlighting")
assert(#vim.lsp.get_clients({ bufnr = big }) == 0, "Large file attached a language server")

vim.cmd.edit(vim.env.NVIM_TEST_MINIFIED)
assert(vim.bo.filetype == "bigfile", "Minified file was not classified as bigfile")
assert(vim.b.completion == false and not vim.treesitter.highlighter.active[vim.api.nvim_get_current_buf()])

assert(not require("noice.config").options.lsp.signature.enabled, "Two automatic signature providers are enabled")
assert(not require("lazy.core.config").plugins["grug-far.nvim"], "Excluded search/replace plugin was enabled")

press(":")
wait_until(function()
  local trigger = package.loaded["blink.cmp.completion.trigger"]
  return vim.api.nvim_get_mode().mode == "c" and trigger and trigger.cmdline_events
end, "Blink did not load for the command line")
press("VimShort")
local cmp = require("blink.cmp")
wait_until(function()
  return cmp.is_menu_visible() and cmp.is_ghost_text_visible() and require("noice.ui.cmdline").position
end, "Floating command line did not show completion and ghost text")
local position = require("noice.ui.cmdline").position
assert(vim.api.nvim_win_get_config(position.win).relative ~= "", "Command line is not floating")
assert(vim.fn.getcmdline() == "VimShort", "Ghost text modified the typed command")
assert(not cmp.get_selected_item(), "Command candidate was preselected")
press("<Tab>")
wait_until(function() return vim.fn.getcmdline() == "VimShortcuts" end, "Tab did not accept completion")
press("<Esc>")
wait_until(function() return vim.api.nvim_get_mode().mode == "n" end, "Escape did not cancel command input")
assert(vim.fn.bufnr("Vim shortcuts") == -1, "Command completion executed the command")

vim.cmd.edit(vim.env.NVIM_TEST_LUA)
local source = vim.api.nvim_get_current_buf()
assert(vim.bo.filetype == "lua", "Large-file detection affected ordinary Lua files")
assert(require("blink.cmp.config").enabled(), "Completion stayed disabled in an ordinary file")
wait_until(function()
  for _, client in ipairs(vim.lsp.get_clients({ bufnr = source })) do
    if client.name == "lua_ls" and client.initialized then return true end
  end
  return false
end, "The installed Lua language server did not attach")
wait_until(function() return vim.treesitter.highlighter.active[source] ~= nil end, "Ordinary Lua lost Treesitter")
assert(vim.fn.maparg("]]", "n", false, true).desc == "Move to @class.outer", "Reference highlighting replaced class navigation")
assert(vim.fn.maparg("[[", "n", false, true).desc == "Move to @class.outer")
press("5G0w")
local function references()
  local count = 0
  for name, namespace in pairs(vim.api.nvim_get_namespaces()) do
    if name == "nvim.lsp.references" or name == "vim_lsp_references" then
      count = count + #vim.api.nvim_buf_get_extmarks(source, namespace, 0, -1, {})
    end
  end
  return count
end
wait_until(function() return references() >= 2 end, "Symbol references were not highlighted automatically")

press("Gi")
wait_until(function() return vim.api.nvim_get_mode().mode == "i" end, "Insert mode did not start")
press("combine")
wait_until(function() return vim.api.nvim_get_current_line() == "combine" end, "Function name was not typed")
press("(")
local signature = require("blink.cmp.signature.window")
wait_until(function() return signature.win:is_open() end, "Function parameters did not appear automatically")
local signature_text = table.concat(vim.api.nvim_buf_get_lines(signature.win:get_buf(), 0, -1, false), "\n")
assert(signature_text:find("first", 1, true) and signature_text:find("second", 1, true), "Signature omitted function parameters")
press("<Esc>")
wait_until(function() return vim.api.nvim_get_mode().mode == "n" and not signature.win:is_open() end,
  "Signature popup did not close after leaving insert mode")
assert(vim.bo[source].modified, "Signature help saved or discarded the typed code")
assert(not vim.o.autowrite and not vim.o.autowriteall and vim.o.clipboard == "")

vim.fn.writefile({ vim.json.encode({ bigfile = true, minified = true, noice_popup = true,
  ghost_text = true, references = true, signature = true, unsaved_edits = true }) }, vim.env.NVIM_TEST_REPORT)
vim.cmd("qa!")
'''

with tempfile.TemporaryDirectory(prefix="nvim-enhancements-tests-", ignore_cleanup_errors=True) as temporary:
    root = Path(temporary).resolve()
    config_home = root / "config"
    config_home.mkdir()
    (config_home / "nvim").symlink_to(CONFIG, target_is_directory=True)
    project = root / "project"
    project.mkdir()
    (project / ".luarc.json").write_text("{}\n")
    source = project / "fixture.lua"
    original = "local function combine(first, second)\n  return first + second\nend\n\nlocal result = combine(1, 2)\nprint(result)\n\n"
    source.write_text(original)
    big = project / "large.lua"
    big.write_text("local value = 1\n" * 140000)
    minified = project / "minified.lua"
    minified.write_text("local value = '" + "x" * 4096 + "'\n")
    environment = dict(os.environ, TERM="xterm-256color", XDG_CONFIG_HOME=str(config_home),
                       XDG_STATE_HOME=str(root / "state"), XDG_CACHE_HOME=str(root / "cache"),
                       NVIM_TEST_LUA=str(source), NVIM_TEST_BIGFILE=str(big),
                       NVIM_TEST_MINIFIED=str(minified))
    for key in list(environment):
        if key.startswith("HERDR_") or key == "NVIM_APPNAME":
            environment.pop(key)
    result = run_probe(CONFIG, root, environment, PROBE)
    assert source.read_text() == original, "Checks changed the file on disk"
    print("Neovim enhancement checks passed:", result)
