return {
  {
    "Saghen/blink.cmp",
    branch = "v1",
    commit = "78336bc89ee5365633bcf754d93df01678b5c08f",
    event = { "InsertEnter", "CmdlineEnter" },
    dependencies = {
      { "rafamadriz/friendly-snippets", commit = "b4d01b0fdf3c9a549961c2f9ffe8dc09be166219" },
    },
    opts = {
      keymap = {
        preset = "enter",
        -- Herdr owns Ctrl-n/p for pane cycling; use arrows in completion menus.
        ["<C-n>"] = false,
        ["<C-p>"] = false,
      },
      completion = {
        list = { selection = { preselect = false, auto_insert = false } },
        documentation = { auto_show = true, auto_show_delay_ms = 300 },
        menu = { border = "rounded" },
        ghost_text = { show_without_selection = true },
      },
      sources = {
        default = { "lazydev", "lsp", "path", "snippets", "buffer" },
        providers = { lazydev = { name = "LazyDev", module = "lazydev.integrations.blink", score_offset = 100 } },
      },
      fuzzy = { implementation = "prefer_rust" },
      signature = { enabled = true, window = { border = "rounded" } },
      cmdline = {
        enabled = true,
        keymap = {
          preset = "cmdline",
          ["<C-n>"] = false,
          ["<C-p>"] = false,
          ["<Right>"] = false,
          ["<Left>"] = false,
          ["<Up>"] = { "select_prev", "fallback" },
          ["<Down>"] = { "select_next", "fallback" },
        },
        completion = {
          ghost_text = { enabled = true },
          list = { selection = { preselect = false } },
          menu = {
            auto_show = function()
              return vim.fn.getcmdtype() == ":"
            end,
          },
        },
      },
      term = { enabled = false },
    },
  },
}
