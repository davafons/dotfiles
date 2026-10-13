#!/usr/bin/env python3
"""Check the tooling statusline in a private terminal with real plugins."""

import os
from pathlib import Path
import shutil
import tempfile

from nvim_probe import run_probe

CONFIG = Path(__file__).resolve().parents[1]

PROBE = r"""
local function wait_until(predicate, message)
  local thread = coroutine.running()
  local deadline = vim.uv.now() + 15000
  while not predicate() do
    assert(vim.uv.now() < deadline, message)
    vim.defer_fn(function() assert(coroutine.resume(thread)) end, 20)
    coroutine.yield()
  end
end

local function status()
  require('lualine').refresh({place={'statusline'}})
  return vim.api.nvim_eval_statusline(vim.o.statusline, {winid=0, maxwidth=160}).str
end

local function expect(text)
  wait_until(function() return status():find(text, 1, true) end, 'Statusline is missing ' .. text)
end

local function open(name)
  vim.cmd.edit(vim.env.NVIM_TEST_ROOT .. '/' .. name)
end

wait_until(function() return package.loaded['lualine'] end, 'Lualine did not load')
open('notes.md')
expect('fmt:prettier')
expect('lsp:marksman')
assert(not status():find('lua_ls', 1, true), 'Statusline lists an unattached language server')
for _, server in ipairs(vim.lsp.get_clients({bufnr=0})) do
  vim.lsp.buf_detach_client(0, server.id)
end
expect('lsp:none')
vim.api.nvim_exec_autocmds('FileType', {buffer=0})
expect('lsp:marksman')
vim.api.nvim_buf_set_lines(0, -1, -1, false, {'Unsaved text'})
local notes = vim.api.nvim_get_current_buf()
assert(vim.bo.modified)

local native_system = vim.system
local probes = 0
local delayed
local hold = true
vim.system = function(argv, options, callback)
  local probe = argv[2] == 'format' and options and options.stdin == ''
  if probe then
    probes = probes + 1
    assert(callback, 'Statusline availability probe is synchronous')
    if hold then
      hold = false
      return native_system(argv, options, function(result)
        delayed = function() callback(result) end
      end)
    end
  end
  return native_system(argv, options, callback)
end

open('project/sample.js')
expect('fmt:biome(checking)')
wait_until(function() return delayed end, 'Native Biome availability probe did not finish')
vim.fn.writefile({'{"formatter":{"enabled":false}}'}, vim.env.NVIM_TEST_ROOT .. '/project/biome.json')
vim.api.nvim_exec_autocmds('BufWritePost', {buffer=0})
expect('fmt:biome(unavailable)')
delayed()
vim.schedule(function() vim.g.statusline_old_result_delivered = true end)
wait_until(function() return vim.g.statusline_old_result_delivered end, 'Old probe was not delivered')
assert(status():find('fmt:biome(unavailable)', 1, true), 'Stale probe overwrote the current status')

vim.fn.writefile({'{"formatter":{"enabled":true}}'}, vim.env.NVIM_TEST_ROOT .. '/project/biome.json')
vim.api.nvim_exec_autocmds('BufWritePost', {buffer=0})
expect('fmt:biome ')
local before = probes
for _ = 1, 50 do status() end
assert(probes == before, 'Statusline redraw started formatter processes')

local conform = require('conform')
conform.formatters.biome.command = vim.env.NVIM_TEST_ROOT .. '/missing-biome'
vim.api.nvim_exec_autocmds('BufWritePost', {buffer=0})
expect('fmt:biome(missing)')
conform.formatters.biome.command = nil
vim.api.nvim_exec_autocmds('BufWritePost', {buffer=0})
expect('fmt:biome ')
conform.formatters.prettier.command = vim.env.NVIM_TEST_ROOT .. '/missing-prettier'
open('missing.md')
expect('fmt:prettier(missing)')
conform.formatters.prettier.command = nil
conform.formatters.prettier.cwd = function() return nil end
conform.formatters.prettier.require_cwd = true
vim.api.nvim_exec_autocmds('BufWritePost', {buffer=0})
expect('fmt:prettier(no-root)')
conform.formatters.prettier.cwd = nil
conform.formatters.prettier.require_cwd = nil
open('notes.md')
expect('fmt:prettier')
assert(vim.api.nvim_get_current_buf() == notes and vim.bo.modified, 'Statusline discarded unsaved edits')
assert(vim.api.nvim_buf_get_lines(0, -2, -1, false)[1] == 'Unsaved text')

open('unknown.custom')
expect('fmt:none')
expect('lsp:none')
assert(not status():find('marksman', 1, true), 'Statusline retained another buffer\'s server')
vim.cmd.enew()
vim.bo.buftype = 'nofile'
vim.bo.filetype = 'markdown'
expect('fmt:none')

open('notes.md')
expect('fmt:prettier')
expect('lsp:marksman')
vim.cmd.redraw()
local screen = {}
for row = 1, vim.o.lines do
  local cells = {}
  for column = 1, vim.o.columns do cells[#cells + 1] = vim.fn.screenstring(row, column) end
  screen[#screen + 1] = table.concat(cells)
end
vim.fn.writefile(screen, vim.env.NVIM_TEST_SCREEN)
local drawn = table.concat(screen, '\n')
assert(drawn:find('fmt:prettier', 1, true) and drawn:find('lsp:marksman', 1, true), 'Tooling badges were not drawn')
assert(not vim.o.autowrite and not vim.o.autowriteall and vim.o.clipboard == '')
vim.system = native_system
vim.fn.writefile({vim.json.encode({statusline=true, attached_only=true, unavailable=true,
  redraw_cached=true, stale_probe=true, unsaved=true})}, vim.env.NVIM_TEST_REPORT)
vim.cmd('qa!')
"""

with tempfile.TemporaryDirectory(prefix="nvim-statusline-tests-") as temporary:
    root = Path(temporary).resolve()
    config_home = root / "config"
    config_home.mkdir()
    (config_home / "nvim").symlink_to(CONFIG, target_is_directory=True)
    (root / ".git").mkdir()
    (root / "project").mkdir()
    files = {
        "notes.md": "# Notes\n\nSaved text.\n",
        "missing.md": "# Missing\n",
        "unknown.custom": "Do not change this.\n",
        "project/sample.js": "const value = 1;\n",
    }
    for name, content in files.items():
        (root / name).write_text(content)
    (root / "project/biome.json").write_text('{"formatter":{"enabled":true}}\n')
    evidence = Path(tempfile.mkdtemp(prefix="nvim-statusline-evidence-"))
    environment = dict(
        os.environ,
        XDG_CONFIG_HOME=str(config_home),
        XDG_STATE_HOME=str(root / "state"),
        XDG_CACHE_HOME=str(root / "cache"),
        NVIM_TEST_ROOT=str(root),
        NVIM_TEST_SCREEN=str(evidence / "screen.txt"),
    )
    for key in list(environment):
        if key.startswith("HERDR_") or key == "NVIM_APPNAME":
            environment.pop(key)
    try:
        result = run_probe(CONFIG, root, environment, PROBE)
        for name, content in files.items():
            assert (root / name).read_text() == content, f"Statusline changed {name} on disk"
    finally:
        shutil.copytree(root, evidence / "fixture", symlinks=True)
        print(f"Statusline evidence retained at {evidence}")
    print("Statusline checks passed:", result)
