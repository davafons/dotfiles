local M = { async_conditions = {} }
local snapshots = {}

local function cancel(snapshot)
  for _, job in pairs(snapshot and snapshot.jobs or {}) do
    job:kill(15)
  end
end

local function label(name, available, reason)
  return name .. (available and "" or "(" .. (reason or "unavailable") .. ")")
end

local function publish(buffer, snapshot)
  if snapshots[buffer] ~= snapshot then
    return
  end
  snapshot.text = #snapshot.labels > 0 and "fmt:" .. table.concat(snapshot.labels, "+") or "fmt:none"
  require("lualine").refresh({ place = { "statusline" } })
end

local function update(buffer)
  cancel(snapshots[buffer])
  local snapshot = { labels = {}, jobs = {}, text = "fmt:none" }
  snapshots[buffer] = snapshot
  if not vim.api.nvim_buf_is_valid(buffer) or vim.bo[buffer].buftype ~= "" then
    publish(buffer, snapshot)
    return
  end
  local conform = require("conform")
  for index, name in ipairs(conform.list_formatters_for_buffer(buffer)) do
    local config = conform.get_formatter_config(name, buffer)
    local check_async = M.async_conditions[name]
    if config and config.command and check_async then
      snapshot.labels[index] = label(name, false, "checking")
      local context = require("conform.runner").build_context(buffer, config)
      snapshot.jobs[index] = check_async(config, context, function(available, reason)
        vim.schedule(function()
          if snapshots[buffer] ~= snapshot then
            return
          end
          snapshot.jobs[index] = nil
          snapshot.labels[index] = label(name, available, reason)
          publish(buffer, snapshot)
        end)
      end)
    else
      local info = conform.get_formatter_info(name, buffer)
      local message = info.available_msg or ""
      local reason = message == "Root directory not found" and "no-root"
        or (message:match("^Command .+ not found$") and "missing" or "unavailable")
      snapshot.labels[index] = label(name, info.available, reason)
    end
  end
  publish(buffer, snapshot)
end

function M.formatter()
  local snapshot = snapshots[vim.api.nvim_get_current_buf()]
  return snapshot and snapshot.text or "fmt:checking"
end

function M.setup()
  for _, snapshot in pairs(snapshots) do
    cancel(snapshot)
  end
  snapshots = {}
  local group = vim.api.nvim_create_augroup("PersonalToolStatus", { clear = true })
  vim.api.nvim_create_autocmd({ "BufEnter", "FileType", "BufFilePost" }, {
    group = group,
    callback = function(event)
      update(event.buf)
    end,
  })
  vim.api.nvim_create_autocmd({ "BufWritePost", "DirChanged", "FocusGained" }, {
    group = group,
    callback = function()
      for _, snapshot in pairs(snapshots) do
        cancel(snapshot)
      end
      snapshots = {}
      update(vim.api.nvim_get_current_buf())
    end,
  })
  vim.api.nvim_create_autocmd("BufWipeout", {
    group = group,
    callback = function(event)
      cancel(snapshots[event.buf])
      snapshots[event.buf] = nil
    end,
  })
  vim.api.nvim_create_autocmd("VimLeavePre", {
    group = group,
    callback = function()
      for _, snapshot in pairs(snapshots) do
        cancel(snapshot)
      end
      snapshots = {}
    end,
  })
  vim.schedule(function()
    update(vim.api.nvim_get_current_buf())
  end)
end

return M
