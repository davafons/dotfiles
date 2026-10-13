#!/usr/bin/env python3
"""Exercise Markdown rendering and preview splits with the installed plugins."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

CONFIG = Path(__file__).resolve().parents[1]
NVIM = shutil.which("nvim")
assert NVIM, "Neovim is required"

PROBE = r'''
local function wait_until(predicate, message)
  local thread = coroutine.running()
  local deadline = vim.uv.now() + 4000
  while not predicate() do
    assert(vim.uv.now() < deadline, message)
    vim.defer_fn(function() assert(coroutine.resume(thread)) end, 10)
    coroutine.yield()
  end
end

local function marks(buffer)
  local count = 0
  for name, namespace in pairs(vim.api.nvim_get_namespaces()) do
    if name:match("^markview/") then
      count = count + #vim.api.nvim_buf_get_extmarks(buffer, namespace, 0, -1, {})
    end
  end
  return count
end

local function marks_at(buffer, row)
  local namespace = vim.api.nvim_get_namespaces()["markview/markdown"]
  if not namespace then return 0 end
  return #vim.api.nvim_buf_get_extmarks(buffer, namespace, { row, 0 }, { row, -1 }, {})
end

local function press(keys)
  vim.api.nvim_input(vim.api.nvim_replace_termcodes(keys, true, false, true))
end

vim.o.columns = 160
vim.o.lines = 50
vim.cmd.edit(vim.env.NVIM_TEST_MARKDOWN)
local source = vim.api.nvim_get_current_buf()
local source_window = vim.api.nvim_get_current_win()
wait_until(function() return vim.fn.exists(":Markview") == 2 end, "Markview command is missing")
assert(not package.loaded["render-markdown"], "The previous renderer is still loaded")
assert(vim.fn.maparg(",mp", "n", false, true).desc == "Toggle Markdown rendering")
assert(vim.fn.maparg(",ms", "n", false, true).desc == "Toggle Markdown preview split")
wait_until(function() return marks(source) > 0 end, "Markdown did not render automatically")
assert(vim.wo.wrap, "Markdown rendering disabled screen wrapping")
wait_until(function()
  local heading = vim.api.nvim_get_hl(0, { name = "MarkviewHeading1", link = false })
  return heading.fg and heading.bg
end, "Markview heading colors were not initialized")
assert(not vim.fn.maparg("gx", "n"):find("Markview", 1, true), "Markview replaced native gx")

press(",mp")
wait_until(function() return marks(source) == 0 end, "Toggle did not remove Markdown rendering")
press(",mp")
wait_until(function() return marks(source) > 0 end, "Toggle did not restore Markdown rendering")

press("GoUnsaved preview text<Esc>")
wait_until(function()
  return vim.api.nvim_get_mode().mode == "n" and vim.api.nvim_buf_get_lines(source, -2, -1, false)[1] == "Unsaved preview text"
end, "Typing did not change the source buffer")
assert(vim.bo[source].modified)
press("Go# Hybrid heading")
wait_until(function()
  local row = vim.api.nvim_win_get_cursor(source_window)[1] - 1
  return vim.api.nvim_get_mode().mode == "i" and
    vim.api.nvim_buf_get_lines(source, row, row + 1, false)[1] == "# Hybrid heading" and
    marks(source) > 0 and marks_at(source, row) == 0
end, "Hybrid editing did not keep the current heading raw and other lines rendered")
press("<Esc>k")
wait_until(function()
  local row = vim.api.nvim_buf_line_count(source) - 1
  return vim.api.nvim_get_mode().mode == "n" and marks_at(source, row) > 0
end, "Heading did not render after moving away from the edited line")
local edited = vim.api.nvim_buf_get_lines(source, 0, -1, false)
local cursor = vim.api.nvim_win_get_cursor(source_window)
local original_windows = #vim.api.nvim_tabpage_list_wins(0)
press(",ms")
wait_until(function() return #vim.api.nvim_tabpage_list_wins(0) == original_windows + 1 end,
  "Preview split did not open")
assert(vim.api.nvim_get_current_win() == source_window, "Opening preview moved editing focus")
assert(vim.deep_equal(vim.api.nvim_win_get_cursor(source_window), cursor), "Opening preview moved the cursor")
local preview_window
for _, window in ipairs(vim.api.nvim_tabpage_list_wins(0)) do
  if window ~= source_window then preview_window = window end
end
local preview = vim.api.nvim_win_get_buf(preview_window)
assert(preview ~= source, "Preview must not reuse the editable source buffer")
assert(vim.api.nvim_win_get_position(preview_window)[2] > vim.api.nvim_win_get_position(source_window)[2],
  "Preview did not open to the right")
wait_until(function()
  return vim.deep_equal(vim.api.nvim_buf_get_lines(preview, 0, -1, false), edited) and marks(preview) > 0
end, "Preview did not render the unsaved source")
assert(not vim.wo[preview_window].number and not vim.wo[preview_window].relativenumber)
assert(not vim.wo[preview_window].list, "Preview contains editor whitespace markers")

press("GoAnother unsaved line<Esc>")
wait_until(function()
  return vim.api.nvim_get_mode().mode == "n" and vim.api.nvim_buf_get_lines(preview, -2, -1, false)[1] == "Another unsaved line"
end, "Preview did not update while editing")
press("dd")
wait_until(function()
  return vim.deep_equal(vim.api.nvim_buf_get_lines(preview, 0, -1, false), edited)
end, "Preview did not shrink after deleting a line")
vim.api.nvim_set_current_win(preview_window)
press(",ms")
wait_until(function() return #vim.api.nvim_tabpage_list_wins(0) == original_windows end,
  "Preview toggle did not close the split")
assert(vim.api.nvim_get_current_buf() == source, "Closing preview did not return to the source")
assert(vim.deep_equal(vim.api.nvim_buf_get_lines(source, 0, -1, false), edited), "Closing preview lost edits")
assert(vim.bo[source].modified, "Preview saved or discarded the source")
wait_until(function() return marks(source) > 0 end, "Inline rendering did not resume after closing preview")

vim.cmd.enew()
vim.bo.filetype = "text"
assert(vim.fn.maparg(",mp", "n") == "" and vim.fn.maparg(",ms", "n") == "",
  "Markdown shortcuts leaked into a non-Markdown buffer")
assert(not vim.o.autowrite and not vim.o.autowriteall and vim.o.clipboard == "")
print("Markdown checks passed: rendering, toggle, colors, wrapping, live split updates, focus, unsaved edits")
vim.cmd("qa!")
'''

with tempfile.TemporaryDirectory(prefix="nvim-markdown-tests-") as temporary:
    root = Path(temporary).resolve()
    config_home = root / "config"
    config_home.mkdir()
    (config_home / "nvim").symlink_to(CONFIG, target_is_directory=True)
    source = root / "notes.md"
    original = "# Reading test\n\nSome **bold** and *italic* text.\n\n## Tasks\n\n- [ ] A task\n\n| A | B |\n| --- | --- |\n| One | Two |\n\n```lua\nprint('hello')\n```\n"
    source.write_text(original)
    probe = root / "probe.lua"
    probe.write_text(PROBE)
    environment = dict(os.environ, XDG_CONFIG_HOME=str(config_home),
                       XDG_STATE_HOME=str(root / "state"), XDG_CACHE_HOME=str(root / "cache"),
                       NVIM_TEST_MARKDOWN=str(source))
    for key in list(environment):
        if key.startswith("HERDR_") or key == "NVIM_APPNAME":
            environment.pop(key)
    command = "lua coroutine.wrap(function() local ok, err = pcall(assert(loadfile(" + json.dumps(str(probe)) + "))); " \
              "if not ok then io.stderr:write(tostring(err) .. '\\n'); vim.cmd('cquit 1') end end)()"
    result = subprocess.run([NVIM, "--headless", "-n", "-i", "NONE", "-u", str(CONFIG / "init.lua"),
                             "-c", command], env=environment, cwd=root,
                            capture_output=True, text=True, timeout=30)
    print(result.stdout + result.stderr, end="")
    if result.returncode:
        raise SystemExit(result.returncode)
    assert "Markdown checks passed:" in result.stdout + result.stderr, "Markdown probe did not complete"
    assert source.read_text() == original, "Preview modified the file on disk"
