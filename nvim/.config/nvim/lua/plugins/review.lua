return {
  {
    "esmuellert/codediff.nvim",
    commit = "09d9ebef2cc5a5c04db7a349cd6c61bdf84ecc8e",
    cmd = "CodeDiff",
    config = function(_, opts)
      require("codediff").setup(opts)
      -- CodeDiff 09d9ebef passes a nil hidden-panel handle to nvim_win_is_valid.
      local actions = require("codediff.ui.explorer")
      for _, name in ipairs({ "navigate_next", "navigate_prev" }) do
        local navigate = actions[name]
        actions[name] = function(explorer)
          if not explorer.winid then
            explorer = vim.tbl_extend("force", explorer, { winid = -1 })
          end
          return navigate(explorer)
        end
      end
    end,
    opts = {
      diff = { layout = "inline" },
      explorer = { hidden = true, initial_focus = "modified" },
      keymaps = {
        view = {
          focus_explorer = false,
          toggle_stage = false,
          toggle_staged_view = false,
          stage_hunk = false,
          unstage_hunk = false,
          discard_hunk = false,
          diff_get = false,
          diff_put = false,
        },
        explorer = { stage_all = false, unstage_all = false, restore = false },
      },
    },
  },
  {
    "NicolasGB/jj.nvim",
    commit = "64605c84f4e7774ff510d614204625ced87ffb48",
    dependencies = { "esmuellert/codediff.nvim" },
    cmd = { "J", "Jdiff", "Jhdiff" },
    keys = {
      { "<leader>jl", "<cmd>J log<CR>", desc = "JJ change log" },
      { "<leader>js", "<cmd>J status<CR>", desc = "JJ status" },
      {
        "<leader>jd",
        function()
          require("jj.diff").show_revision({ rev = "@" })
        end,
        desc = "Review current JJ change",
      },
      {
        "<leader>jf",
        function()
          require("jj.diff").diff_current({ rev = "@-" })
        end,
        desc = "Review current file against JJ parent",
      },
      -- The upstream CodeDiff backend takes target first, then base.
      {
        "<leader>jm",
        function()
          require("jj.diff").diff_revisions({ left = "@", right = "main" })
        end,
        desc = "Review JJ changes since main",
      },
    },
    opts = {
      diff = { backend = "codediff" },
      -- Use David's `jj push` alias in a shell to run the required checks.
      cmd = { keymaps = { log = { push = false, push_all = false } } },
    },
  },
}
