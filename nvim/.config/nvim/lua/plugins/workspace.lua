return {
  {
    "folke/persistence.nvim",
    commit = "b20b2a7887bd39c1a356980b45e03250f3dce49c",
    event = "BufReadPre",
    opts = { branch = false }, -- A session per project directory also works with jj.
    keys = {
      {
        "<leader>qs",
        function()
          require("persistence").load()
        end,
        desc = "Restore project session",
      },
      {
        "<leader>qS",
        function()
          require("persistence").select()
        end,
        desc = "Select session",
      },
      {
        "<leader>ql",
        function()
          require("persistence").load({ last = true })
        end,
        desc = "Restore last session",
      },
      {
        "<leader>qd",
        function()
          require("persistence").stop()
        end,
        desc = "Stop session saving",
      },
    },
  },
  {
    "folke/snacks.nvim",
    commit = "882c996cf28183f4d63640de0b4c02ec886d01f2",
    dependencies = { "akinsho/bufferline.nvim", "nvim-lualine/lualine.nvim" },
    priority = 900,
    lazy = false,
    opts = {
      bigfile = { enabled = true },
      words = { enabled = true },
      indent = { enabled = true, animate = { enabled = false } },
      dashboard = {
        enabled = true,
        preset = {
          pick = function(cmd, opts)
            if cmd == "files" or cmd == "live_grep" then
              require("config.projects").search(cmd, opts)
            else
              require("fzf-lua")[cmd](opts)
            end
          end,
          keys = {
            { icon = " ", key = "f", desc = "Find File", action = ":lua Snacks.dashboard.pick('files')" },
            { icon = " ", key = "n", desc = "New File", action = ":ene | startinsert" },
            { icon = " ", key = "g", desc = "Find Text", action = ":lua Snacks.dashboard.pick('live_grep')" },
            { icon = " ", key = "r", desc = "Recent Files", action = ":lua Snacks.dashboard.pick('oldfiles')" },
            { icon = " ", key = "p", desc = "Projects", action = ":lua require('config.projects').pick()" },
            {
              icon = " ",
              key = "c",
              desc = "Config",
              action = ":lua Snacks.dashboard.pick('files', {cwd = vim.fn.stdpath('config')})",
            },
            { icon = " ", key = "s", desc = "Restore Session", section = "session" },
            { icon = "󰒲 ", key = "l", desc = "Plugins", action = ":Lazy" },
            { icon = "󰋖 ", key = "?", desc = "Vim Shortcuts", action = ":VimShortcuts" },
            { icon = " ", key = "q", desc = "Quit", action = ":qa" },
          },
        },
        sections = {
          { section = "header" },
          { section = "keys", gap = 0, padding = 1 },
          {
            text = {
              { "LEARN VIM  ", hl = "title" },
              { "operator + motion + repeat", hl = "desc" },
            },
          },
          { text = 'ciw change word   di" delete inside quotes   . repeat' },
          { text = ",tt files   ,tg search   ,jd review   ,ac ask agent" },
          { text = ",h full guide   / search the guide   q return", padding = 1 },
          { section = "startup" },
        },
      },
    },
  },
  {
    "OXY2DEV/markview.nvim",
    commit = "49d2cf7ced872db74083a144ded1f94fe224d09a",
    lazy = false,
    dependencies = { "nvim-treesitter/nvim-treesitter", "nvim-tree/nvim-web-devicons" },
    opts = function()
      local headings = { shift_width = 0 }
      for level = 1, 6 do
        headings["heading_" .. level] = { style = "icon", icon = "", sign = "" }
      end
      for level = 1, 2 do
        headings["setext_" .. level] = { icon = "", sign = "", border = " " }
      end
      return {
        preview = {
          filetypes = { "markdown" },
          modes = { "n", "no", "c", "i" },
          hybrid_modes = { "n", "i" },
          linewise_hybrid_mode = true,
          icon_provider = "devicons",
          map_gx = false,
        },
        markdown = {
          headings = headings,
          list_items = {
            marker_minus = { text = "•" },
            marker_plus = { text = "•" },
            marker_star = { text = "•" },
          },
        },
        markdown_inline = {
          inline_codes = { padding_left = "", padding_right = "" },
        },
      }
    end,
    keys = {
      {
        "<leader>mp",
        "<cmd>Markview toggle<cr>",
        desc = "Toggle Markdown rendering",
        ft = "markdown",
      },
      {
        "<leader>ms",
        "<cmd>Markview splitToggle<cr>",
        desc = "Toggle Markdown preview split",
        ft = "markdown",
      },
      {
        "<leader>mv",
        "<cmd>McatPreview<cr>",
        desc = "Preview Markdown in Ghostty",
        ft = "markdown",
      },
    },
    config = function(_, opts)
      require("markview").setup(opts)
      require("config.markdown_preview").setup()
    end,
  },
}
