local M = {}
local launching = false

local script = [[
on run argv
  if not (application id "com.mitchellh.ghostty" is running) then
    error "Open Neovim in Ghostty before launching a preview."
  end if
  tell application id "com.mitchellh.ghostty"
    if not frontmost then
      error "Run the preview shortcut from the active Ghostty window."
    end if
    set sourceTerminal to focused terminal of selected tab of front window
    set previewConfig to {initial working directory:item 1 of argv, command:item 2 of argv, wait after command:false}
    set previewTerminal to split sourceTerminal direction right with configuration previewConfig
    return id of previewTerminal
  end tell
end run
]]

local function notify(message)
  vim.notify(message, vim.log.levels.WARN, { title = "Markdown preview" })
end

function M.open()
  if launching then
    notify("A Markdown preview is already launching.")
    return
  end
  if vim.fn.has("mac") ~= 1 then
    notify("The native Ghostty preview requires macOS.")
    return
  end
  local path = vim.api.nvim_buf_get_name(0)
  if vim.bo.filetype ~= "markdown" or vim.bo.buftype ~= "" or path == "" then
    notify("Open a saved Markdown file before launching a preview.")
    return
  end
  if vim.bo.modified then
    notify("Save this file with :w before opening the mcat preview.")
    return
  end
  local stat = vim.uv.fs_stat(path)
  if not stat or stat.type ~= "file" then
    notify("Save this file with :w before opening the mcat preview.")
    return
  end
  local mcat = vim.fn.exepath("mcat")
  if mcat == "" then
    notify("mcat is missing. Install it with brew install mcat.")
    return
  end
  local osascript = vim.fn.exepath("osascript")
  if osascript == "" then
    notify("osascript is missing; native Ghostty previews are unavailable.")
    return
  end
  local command = table.concat(vim.tbl_map(vim.fn.shellescape, { mcat, "-I", "--kitty", "--", path }), " ")
  launching = true
  local ok, err = pcall(vim.system, { osascript, "-", vim.fs.dirname(path), command }, {
    stdin = script,
    text = true,
    timeout = 10000,
  }, function(result)
    vim.schedule(function()
      launching = false
      if result.code ~= 0 then
        local message = vim.trim(result.stderr or "")
        notify(message ~= "" and message or "Ghostty could not open the Markdown preview.")
      end
    end)
  end)
  if not ok then
    launching = false
    notify("Could not launch the Markdown preview: " .. tostring(err))
  end
end

function M.setup()
  vim.api.nvim_create_user_command("McatPreview", M.open, { desc = "Preview Markdown in a native Ghostty split" })
end

return M
