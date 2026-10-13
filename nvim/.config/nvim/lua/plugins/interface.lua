return {
  {
    "nvim-tree/nvim-web-devicons",
    commit = "58447c1fca354bbf184425e4a8d01deecbd6f3c4",
    lazy = true,
    opts = {},
  },
  {
    "folke/noice.nvim",
    commit = "7bfd942445fb63089b59f97ca487d605e715f155",
    event = { "VeryLazy", "CmdlineEnter" },
    cmd = "Noice",
    dependencies = {
      { "MunifTanjim/nui.nvim", commit = "de740991c12411b663994b2860f1a4fd0937c130" },
    },
    opts = {
      lsp = {
        hover = { enabled = false },
        signature = { enabled = false },
      },
      presets = {
        bottom_search = true,
        command_palette = true,
        long_message_to_split = true,
      },
    },
  },
  {
    "akinsho/bufferline.nvim",
    commit = "655133c3b4c3e5e05ec549b9f8cc2894ac6f51b3",
    event = "VeryLazy",
    dependencies = { "nvim-tree/nvim-web-devicons" },
    opts = {
      options = {
        mode = "buffers",
        themable = false,
        diagnostics = "nvim_lsp",
        numbers = "buffer_id",
        offsets = { { filetype = "NvimTree", text = "Files", text_align = "left" } },
      },
    },
  },
  {
    "nvim-lualine/lualine.nvim",
    commit = "221ce6b2d999187044529f49da6554a92f740a96",
    event = "VeryLazy",
    dependencies = { "nvim-tree/nvim-web-devicons" },
    opts = {
      options = {
        theme = "auto",
        globalstatus = true,
        disabled_filetypes = { statusline = { "NvimTree", "snacks_dashboard" } },
      },
      sections = {
        lualine_a = { "mode" },
        lualine_b = { "diagnostics" },
        lualine_c = { { "filename", path = 1 } },
        lualine_x = { "filetype" },
        lualine_y = { "progress" },
        lualine_z = { "location" },
      },
    },
  },
}
