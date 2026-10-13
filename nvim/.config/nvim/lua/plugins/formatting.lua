local function lint_buffer()
  if vim.bo.buftype ~= "" then
    return
  end
  local lint = require("lint")
  local available = {}
  local filetype = vim.bo.filetype
  local names = lint.linters_by_ft[filetype] or lint.linters_by_ft[filetype:match("^[^.]+") or ""] or {}
  for _, name in ipairs(names) do
    local linter = lint.linters[name]
    local command = type(linter.cmd) == "function" and linter.cmd() or linter.cmd
    if vim.fn.executable(command) == 1 then
      table.insert(available, name)
    end
  end
  if #available > 0 then
    local filename = vim.api.nvim_buf_get_name(0)
    local directory = filename ~= "" and vim.fs.dirname(filename) or vim.fn.getcwd()
    lint.try_lint(available, { cwd = directory, filter = vim.bo.modified and "stdin" or nil })
  end
end

return {
  {
    "stevearc/conform.nvim",
    commit = "016802de402556da54c36bd7359b441266b01cdd",
    cmd = "ConformInfo",
    keys = {
      {
        "<leader>cf",
        function()
          require("conform").format({ async = true, lsp_format = "never" })
        end,
        mode = { "n", "x" },
        desc = "Format buffer or selection",
      },
    },
    opts = function()
      local util = require("conform.util")
      local scripts = {
        javascript = { extension = ".js", parser = "babel" },
        typescript = { extension = ".ts", parser = "typescript" },
        javascriptreact = { extension = ".jsx", parser = "babel" },
        typescriptreact = { extension = ".tsx", parser = "typescript" },
      }
      local function script_type(ctx)
        return vim.fn.fnamemodify(ctx.filename, ":e") == "" and scripts[vim.bo[ctx.buf].filetype] or nil
      end
      local function biome_path(ctx)
        local script = script_type(ctx)
        return ctx.filename .. (script and script.extension or "")
      end
      local function probe_biome(self, ctx, callback)
        local cwd = self:cwd(ctx)
        local command = type(self.command) == "function" and self.command(self, ctx) or self.command
        if not cwd then
          return nil, "no-root"
        end
        if vim.fn.executable(command) ~= 1 then
          return nil, "missing"
        end
        return vim.system({ command, "format", "--stdin-file-path", biome_path(ctx) }, {
          cwd = cwd,
          stdin = "",
          text = true,
          timeout = 2000,
        }, callback)
      end
      require("config.tool_status").async_conditions.biome = function(self, ctx, callback)
        local process, reason = probe_biome(self, ctx, function(result)
          callback(result.code == 0, "unavailable")
        end)
        if not process then
          callback(false, reason)
        end
        return process
      end
      local function web_formatters(buf)
        if vim.fs.root(buf, { "biome.json", "biome.jsonc" }) then
          return { "biome" }
        end
        return { "prettier" }
      end
      return {
        default_format_opts = { lsp_format = "never" },
        formatters_by_ft = {
          ruby = { "rubocop" },
          rust = { "rustfmt" },
          perl = { "perltidy" },
          eruby = { "herb" },
          lua = { "stylua" },
          sh = { "shfmt" },
          bash = { "shfmt" },
          python = { "ruff_format" },
          kotlin = { "ktlint" },
          java = { "google-java-format" },
          sql = { "sqlfluff" },
          toml = { "taplo" },
          javascript = web_formatters,
          typescript = web_formatters,
          javascriptreact = web_formatters,
          typescriptreact = web_formatters,
          vue = web_formatters,
          svelte = web_formatters,
          html = web_formatters,
          css = web_formatters,
          scss = { "prettier" },
          json = web_formatters,
          jsonc = web_formatters,
          yaml = { "prettier" },
          markdown = { "prettier" },
        },
        formatters = {
          prettier = {
            prepend_args = function(_, ctx)
              local script = script_type(ctx)
              return script and { "--parser", script.parser } or {}
            end,
          },
          biome = {
            require_cwd = true,
            args = function(_, ctx)
              return { "format", "--stdin-file-path", biome_path(ctx) }
            end,
            condition = function(self, ctx)
              local process = probe_biome(self, ctx)
              return process ~= nil and process:wait(2000).code == 0
            end,
          },
          herb = {
            command = util.from_node_modules("herb-format"),
            args = { "-" },
            stdin = true,
            cwd = util.root_file({ ".herb.yml" }),
            require_cwd = true,
          },
          rubocop = {
            cwd = util.root_file({ "Gemfile", ".rubocop.yml" }),
            command = function(_, ctx)
              return vim.fs.root(ctx.dirname, { "Gemfile" }) and "bundle" or "rubocop"
            end,
            prepend_args = function(_, ctx)
              return vim.fs.root(ctx.dirname, { "Gemfile" }) and { "exec", "rubocop" } or {}
            end,
          },
        },
        -- No format_on_save: only explicit ,cf modifies formatting.
      }
    end,
  },
  {
    "mfussenegger/nvim-lint",
    commit = "f6230a5c06ba59e6059c14637f1dbe29a7978b9b",
    event = { "BufReadPost", "BufNewFile" },
    keys = {
      {
        "<leader>cl",
        lint_buffer,
        desc = "Run file linters",
      },
    },
    config = function()
      local lint = require("lint")
      lint.linters_by_ft = {
        markdown = { "markdownlint-cli2" },
        yaml = { "yamllint" },
        make = { "checkmake" },
        python = { "ruff" },
        sh = { "shellcheck" },
        bash = { "shellcheck" },
        dockerfile = { "hadolint" },
        kotlin = { "ktlint" },
      }
      lint.linters["markdownlint-cli2"].cmd = function()
        local filename = vim.api.nvim_buf_get_name(0)
        local directory = filename ~= "" and vim.fs.dirname(filename) or vim.fn.getcwd()
        for _, modules in ipairs(vim.fs.find("node_modules", { path = directory, upward = true, limit = math.huge })) do
          local command = vim.fs.joinpath(modules, ".bin/markdownlint-cli2")
          if vim.fn.executable(command) == 1 then
            return command
          end
        end
        return "markdownlint-cli2"
      end
      lint.linters.shellcheck.args = {
        "--format",
        "json1",
        "--shell",
        function()
          return vim.b.is_bash == 1 and "bash" or "sh"
        end,
        "-",
      }
      vim.api.nvim_create_autocmd({ "BufReadPost", "FileType", "BufWritePost" }, {
        group = vim.api.nvim_create_augroup("PersonalLint", { clear = true }),
        callback = function(ev)
          vim.api.nvim_buf_call(ev.buf, lint_buffer)
        end,
      })
    end,
  },
}
