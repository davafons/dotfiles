local M = {}
local context
local diff_tab
local files_tab
local lifetime
local owner_closed = false
local shutdown_deadline
local recovered_count = 0
local choosing_target = false

local function notify(message)
  vim.notify(message, vim.log.levels.WARN, { title = "Workspace Code" })
end

local function read_context()
  return vim.json.decode(table.concat(vim.fn.readfile(M.context_path), "\n"), { luanil = { object = true } })
end

local function helper(command, argument, done)
  local args = { "python3", context.launcher, command }
  if argument then
    vim.list_extend(args, type(argument) == "table" and argument or { argument })
  end
  vim.system(args, { text = true, timeout = 15000 }, function(result)
    vim.schedule(function()
      if result.code ~= 0 then
        notify(vim.trim(result.stderr))
      end
      if done then
        done(result.code == 0)
      end
    end)
  end)
end

function M.refresh_context()
  context = read_context()
  local target = context.target
  require("herdr-nvim.ask").set_target(target and { pane_id = target.pane_id, agent = target.agent } or nil)
  local label = "Default agent: choose with ,at"
  if target then
    label = "Default: "
      .. (target.number and "Agent " .. target.number or target.agent)
      .. " ("
      .. target.pane_id
      .. ")"
    if target.summary then
      label = label .. " · " .. target.summary:gsub("[\r\n]", " ")
    end
  end
  if recovered_count > 0 then
    label = label .. " · recovered unsaved buffers"
  end
  label = (vim.fn.fnamemodify(context.root, ":t") .. " · " .. label .. " · ,ab return"):gsub("%%", "%%%%")
  for _, win in ipairs(vim.api.nvim_list_wins()) do
    if vim.api.nvim_win_get_config(win).relative == "" then
      vim.wo[win].winbar = label
    end
  end
end

function M.return_to_agent()
  helper("return")
end

function M.tab()
  helper("tab")
end

function M.files()
  if files_tab and vim.api.nvim_tabpage_is_valid(files_tab) then
    vim.api.nvim_set_current_tabpage(files_tab)
  end
  local win = vim.api.nvim_get_current_win()
  require("nvim-tree.api").tree.open({ path = context.root, find_file = true })
  vim.api.nvim_set_current_win(win)
end

function M.toggle_changes()
  if diff_tab and vim.api.nvim_get_current_tabpage() == diff_tab then
    M.files()
  else
    M.changes()
  end
end

function M.changes()
  if diff_tab and vim.api.nvim_tabpage_is_valid(diff_tab) then
    vim.api.nvim_set_current_tabpage(diff_tab)
    return
  end
  if not vim.uv.fs_stat(context.root .. "/.git") then
    notify("Code editing works here, but CodeDiff currently needs a Git-backed checkout.")
    return
  end
  local base = context.kind == "jj" and require("jj.utils").get_commit_id("@-") or "HEAD"
  if not base then
    return
  end
  vim.cmd("CodeDiff " .. base)
end

function M.choose_target(done)
  if choosing_target then
    notify("The recipient picker is already open.")
    if done then
      done(nil)
    end
    return
  end
  choosing_target = true
  local preferred = read_context().target
  local function finish(target)
    choosing_target = false
    if done then
      done(target)
    end
  end
  vim.system({ "herdr", "agent", "list" }, { text = true, timeout = 10000 }, function(result)
    vim.schedule(function()
      local ok, response = pcall(vim.json.decode, result.stdout)
      local agents = ok and response.result and response.result.agents
      if result.code ~= 0 or type(agents) ~= "table" or #agents == 0 then
        notify("No running agents available: " .. vim.trim(result.stderr))
        finish(nil)
        return
      end
      table.sort(agents, function(a, b)
        local a_preferred = preferred and a.pane_id == preferred.pane_id or false
        local b_preferred = preferred and b.pane_id == preferred.pane_id or false
        if a_preferred ~= b_preferred then
          return a_preferred
        end
        local a_here = a.workspace_id == context.workspace_id
        local b_here = b.workspace_id == context.workspace_id
        if a_here ~= b_here then
          return a_here
        end
        local a_number = tonumber((a.tokens or {}).shortcut_number) or 999
        local b_number = tonumber((b.tokens or {}).shortcut_number) or 999
        return a_number < b_number or (a_number == b_number and a.pane_id < b.pane_id)
      end)
      vim.ui.select(agents, {
        prompt = done and "Send tagged code to:" or "Choose default agent:",
        format_item = function(agent)
          local tokens = agent.tokens or {}
          local session = (agent.agent_session or {}).value or tokens.yuke_session_id
          return "Agent "
            .. (tokens.shortcut_number or "?")
            .. " ("
            .. agent.pane_id
            .. ") · "
            .. agent.agent
            .. " · "
            .. agent.agent_status
            .. " · "
            .. (agent.foreground_cwd or agent.cwd or "")
            .. " · "
            .. (tokens.summary or agent.terminal_title_stripped or "")
            .. (session and " · session " .. session or "")
        end,
      }, function(choice)
        if not choice then
          finish(nil)
          return
        end
        helper("target", { choice.pane_id, vim.json.encode(choice) }, function(success)
          if success then
            M.refresh_context()
          end
          finish(success and context.target or nil)
        end)
      end)
    end)
  end)
end

local function same_target(pane, target)
  return pane.agent == target.agent
    and pane.terminal_id == target.terminal_id
    and (not target.session or vim.deep_equal(pane.agent_session, target.session))
    and (not target.yuke_session_id or (pane.tokens or {}).yuke_session_id == target.yuke_session_id)
end

local function guard_delivery()
  local bridge = require("herdr-nvim.bridge")
  local run = bridge.run
  bridge.run = function(config, args, input, on_exit, opts)
    if (args[1] ~= "send" and args[1] ~= "ask") or vim.tbl_contains(args, "--dry-run") then
      return run(config, args, input, on_exit, opts)
    end
    local function deliver(target)
      if not target then
        on_exit(false, "No recipient confirmed. Your tags are kept.")
        return
      end
      local targeted = vim.list_extend({}, args)
      for index, arg in ipairs(args) do
        if arg == "--target" then
          if args[1] == "ask" and args[index + 1] ~= target.pane_id then
            on_exit(false, "The recipient changed. Choose an agent explicitly with ,at.")
            return
          end
          targeted[index + 1] = target.pane_id
        end
      end
      if not vim.tbl_contains(args, "--target") then
        vim.list_extend(targeted, { "--target", target.pane_id })
      end
      vim.system({ "herdr", "pane", "get", target.pane_id }, { text = true, timeout = 10000 }, function(result)
        vim.schedule(function()
          local ok, response = pcall(vim.json.decode, result.stdout)
          local pane = ok and response.result and response.result.pane
          if result.code ~= 0 or not pane or not same_target(pane, target) then
            on_exit(false, "The target agent or session changed. Choose with ,at; your comments are kept.")
            return
          end
          run(config, targeted, input, on_exit, opts)
        end)
      end)
    end
    if args[1] == "send" then
      M.choose_target(deliver)
    else
      deliver(read_context().target)
    end
  end
end

function M.preserve()
  local buffers = {}
  for _, buf in ipairs(vim.api.nvim_list_bufs()) do
    if vim.api.nvim_buf_is_loaded(buf) and vim.bo[buf].modified and vim.bo[buf].buftype == "" then
      table.insert(buffers, {
        name = vim.api.nvim_buf_get_name(buf),
        lines = vim.api.nvim_buf_get_lines(buf, 0, -1, false),
        filetype = vim.bo[buf].filetype,
      })
    end
  end
  local temporary = context.recovery .. ".tmp"
  vim.fn.writefile({}, temporary)
  vim.fn.setfperm(temporary, "rw-------")
  vim.fn.writefile({ vim.json.encode(buffers) }, temporary)
  assert(vim.uv.fs_rename(temporary, context.recovery))
end

local function recover()
  if vim.fn.filereadable(context.recovery) ~= 1 then
    return
  end
  local buffers = vim.json.decode(table.concat(vim.fn.readfile(context.recovery), "\n"))
  for _, saved in ipairs(buffers) do
    local buf = saved.name ~= "" and vim.fn.bufadd(saved.name) or vim.api.nvim_create_buf(true, false)
    vim.fn.bufload(buf)
    vim.api.nvim_buf_set_lines(buf, 0, -1, false, saved.lines)
    vim.bo[buf].filetype = saved.filetype
    vim.bo[buf].modified = true
  end
  recovered_count = #buffers
  if recovered_count > 0 then
    io.stderr:write("Recovered " .. recovered_count .. " unsaved buffer(s); original files were not written.\n")
  end
end

function M.setup()
  if M.context_path then
    return
  end
  M.context_path = assert(vim.env.HERDR_CODE_CONTEXT_PATH, "Missing Code context")
  context = read_context()
  require("lazy").load({ plugins = { "jj.nvim", "codediff.nvim", "herdr-nvim", "fzf-lua" } })
  require("fzf-lua").register_ui_select({
    no_hide = true,
    winopts = { width = 0.9, height = 0.4 },
    fzf_opts = { ["--no-sort"] = false, ["--sort"] = true, ["--tiebreak"] = "index" },
  }, true)
  files_tab = vim.api.nvim_get_current_tabpage()
  guard_delivery()
  recover()
  M.refresh_context()
  lifetime = vim.uv.new_pipe(false)
  assert(lifetime:open(tonumber(vim.env.HERDR_CODE_LIFETIME_FD)))
  lifetime:read_start(function(err, data)
    if err or data == nil then
      lifetime:read_stop()
      lifetime:close()
      shutdown_deadline = vim.uv.new_timer()
      shutdown_deadline:start(3000, 0, function()
        io.stderr:write("Code owner is gone; forced exit because editor shutdown did not finish.\n")
        os.exit(1)
      end)
      vim.schedule(function()
        owner_closed = true
        local ok, failure = pcall(M.preserve)
        if not ok then
          notify("Could not preserve unsaved buffers: " .. tostring(failure))
        end
        vim.cmd("noautocmd qa!")
      end)
    end
  end)
  vim.api.nvim_create_user_command("HerdrCode", M.toggle_changes, {})
  vim.keymap.set("n", "<leader>ab", M.return_to_agent, { desc = "Return to Herdr source pane" })
  vim.keymap.set("n", "<leader>ae", M.tab, { desc = "Open the full Code tab" })
  vim.keymap.set("n", "<leader>ad", M.toggle_changes, { desc = "Files / checkout changes" })
  vim.keymap.set("n", "<leader>as", function()
    require("herdr-nvim").send()
  end, { desc = "Choose recipient and send tagged code" })
  vim.keymap.set("n", "<leader>af", M.files, { desc = "Return to file explorer" })
  vim.keymap.set("n", "<leader>at", M.choose_target, { desc = "Choose default agent" })
  -- Herdr terminal popups forward prefix keys to their application.
  vim.keymap.set("n", "<C-a>e", M.return_to_agent, { desc = "Return from Code overlay" })
  vim.keymap.set("n", "<C-a>E", M.return_to_agent, { desc = "Dismiss Code overlay" })
  vim.keymap.set("n", "<C-a>r", M.changes, { desc = "Checkout changes in overlay" })
  local group = vim.api.nvim_create_augroup("WorkspaceCode", { clear = true })
  vim.api.nvim_create_autocmd("User", {
    group = group,
    pattern = "CodeDiffOpen",
    callback = function(event)
      diff_tab = event.data.tabpage
      M.refresh_context()
    end,
  })
  vim.api.nvim_create_autocmd("User", {
    group = group,
    pattern = "CodeDiffClose",
    callback = function(event)
      if event.data.tabpage == diff_tab then
        diff_tab = nil
      end
    end,
  })
  vim.api.nvim_create_autocmd({ "WinEnter", "TabEnter" }, { group = group, callback = M.refresh_context })
  vim.api.nvim_create_autocmd("QuitPre", {
    group = group,
    callback = function()
      if not owner_closed and #vim.api.nvim_list_uis() == 1 and #vim.api.nvim_tabpage_list_wins(0) == 1 then
        vim.cmd("split")
        vim.schedule(M.return_to_agent)
      end
    end,
  })
  M.files()
  M.refresh_context()
end

return M
