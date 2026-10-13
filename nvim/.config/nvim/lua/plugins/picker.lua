local function find_files()
  require("config.projects").search("files")
end

local function search_text()
  require("config.projects").search("live_grep")
end

return {
  {
    "ibhagwan/fzf-lua",
    commit = "48d7c3db291a2c7c1825905c227a6bc81c83b837",
    cmd = "FzfLua",
    keys = {
      { "<leader><space>", find_files, desc = "Find files" },
      { "<leader>ff", find_files, desc = "Find files" },
      { "<leader>/", search_text, desc = "Search project" },
      { "<leader>sg", search_text, desc = "Search project" },
      { "<leader>tt", find_files, desc = "Find files" },
      { "<leader>tg", search_text, desc = "Search project" },
      {
        "<leader>tb",
        function()
          require("fzf-lua").buffers()
        end,
        desc = "Find open buffers",
      },
      {
        "<leader>tr",
        function()
          require("fzf-lua").oldfiles()
        end,
        desc = "Find recent files",
      },
      {
        "<leader>tp",
        function()
          require("config.projects").pick()
        end,
        desc = "Find recent projects",
      },
    },
    opts = {
      files = { hidden = true, no_ignore = false },
      winopts = { preview = { layout = "flex" } },
    },
  },
}
