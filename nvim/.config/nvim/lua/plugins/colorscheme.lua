return {
  {
    "maxmx03/solarized.nvim",
    commit = "a8085e29883ddcfb39bd46197eb32ef00df05368",
    lazy = false,
    priority = 1000,
    opts = {
      on_highlights = function()
        local palettes = {
          dark = {
            accent = "#4695f7",
            strong = "#cad8d9",
            yellow = "#dbb32d",
            cyan = "#41c7b9",
            green = "#75b938",
            surface = "#0d303a",
          },
          light = {
            accent = "#006599",
            strong = "#203137",
            yellow = "#765c00",
            cyan = "#006f66",
            green = "#3b6b14",
            surface = "#eee8d5",
          },
        }
        local palette = palettes[vim.o.background]
        local highlights = {
          ["@markup.strong.markdown_inline"] = { fg = palette.strong, bg = "NONE", bold = true },
          ["@markup.raw.markdown_inline"] = { fg = palette.yellow, bg = "NONE" },
          ["@markup.list.markdown"] = { fg = palette.accent, bg = "NONE" },
          ["@markup.quote.markdown"] = { fg = palette.green, bg = "NONE" },
          MarkviewInlineCode = { fg = palette.yellow, bg = "NONE" },
          MarkviewCode = { fg = palette.cyan, bg = palette.surface },
          MarkviewBlockQuoteDefault = { fg = palette.green, bg = "NONE" },
        }
        for level = 1, 6 do
          local heading = { fg = palette.accent, bg = "NONE", bold = true }
          highlights["@markup.heading." .. level .. ".markdown"] = heading
          highlights["MarkviewHeading" .. level] = heading
        end
        for _, marker in ipairs({ "Minus", "Plus", "Star" }) do
          highlights["MarkviewListItem" .. marker] = { fg = palette.accent, bg = "NONE" }
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
