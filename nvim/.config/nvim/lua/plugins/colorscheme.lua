return {
  {
    "maxmx03/solarized.nvim",
    commit = "a8085e29883ddcfb39bd46197eb32ef00df05368",
    lazy = false,
    priority = 1000,
    opts = {
      on_highlights = function(colors)
        local highlights = {}
        local foreground = vim.o.background == "dark" and colors.base2 or colors.base02
        for level = 1, 6 do
          highlights["@markup.heading." .. level .. ".markdown"] = { fg = foreground, bold = true }
        end
        return highlights
      end,
    },
    config = function(_, opts)
      vim.opt.termguicolors = true
      vim.opt.background = "dark"
      require("solarized").setup(opts)
      vim.cmd.colorscheme("solarized")
    end,
  },
}
