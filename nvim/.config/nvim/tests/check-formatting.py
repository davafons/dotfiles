#!/usr/bin/env python3
"""Exercise real formatters and linters in a private Neovim terminal."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from nvim_probe import run_probe

CONFIG = Path(__file__).resolve().parents[1]

PROBE = r"""
local function wait_until(predicate, message)
  local thread = coroutine.running()
  local deadline = vim.uv.now() + 15000
  while not predicate() do
    assert(vim.uv.now() < deadline, message)
    vim.defer_fn(function() assert(coroutine.resume(thread)) end, 20)
    coroutine.yield()
  end
end

local function open(name)
  vim.cmd.edit(vim.env.NVIM_TEST_ROOT .. '/' .. name)
  return vim.api.nvim_get_current_buf()
end

local function format(expected)
  vim.api.nvim_input(vim.api.nvim_replace_termcodes(',cf', true, false, true))
  wait_until(function()
    return vim.deep_equal(vim.api.nvim_buf_get_lines(0, 0, -1, false), expected)
  end, 'Mapped formatter did not produce the expected text')
  assert(vim.bo.modified, 'Formatting saved the file')
end

local function client(name)
  wait_until(function()
    return #vim.lsp.get_clients({bufnr=0, name=name}) > 0
  end, 'Missing language server ' .. name)
end

local function language_error(name)
  client(name)
  local buffer = vim.api.nvim_get_current_buf()
  wait_until(function()
    for _, diagnostic in ipairs(vim.diagnostic.get(buffer)) do
      if diagnostic.severity == vim.diagnostic.severity.ERROR then return true end
    end
    return false
  end, 'Missing language-server error for ' .. name)
end

local function lint(source, code)
  local buffer = vim.api.nvim_get_current_buf()
  vim.diagnostic.reset(nil, buffer)
  local key = vim.api.nvim_replace_termcodes(',cl', true, false, true)
  vim.api.nvim_input(key)
  wait_until(function()
    for _, diagnostic in ipairs(vim.diagnostic.get(buffer)) do
      if diagnostic.source == source and (not code or tostring(diagnostic.code) == code) then return true end
    end
    return false
  end, 'Missing ' .. source .. ' diagnostic ' .. tostring(code))
end

open('notes.md')
local formatters = require('conform').list_formatters(0)
assert(#formatters == 1 and formatters[1].name == 'prettier', 'Mason Prettier fallback is missing')
format({'# Heading', '', '- one', '- two'})
vim.api.nvim_buf_set_lines(0, 0, -1, false, {'#Heading', '', '- one'})
lint('markdownlint')

open('sample.py')
format({'value = {"a": 1, "b": 2}'})
vim.api.nvim_buf_set_lines(0, 0, -1, false, {'print(undefined_name)'})
lint('ruff', 'F821')

open('sample.sh')
format({'#!/bin/bash', 'if true; then', '  echo hello', 'fi'})
vim.api.nvim_buf_set_lines(0, 0, -1, false, {'#!/bin/bash', 'echo $undefined_name'})
lint('shellcheck', '2086')

open('sample.lua')
format({'local value = { a = 1, b = 2 }'})

open('sample.json')
format({'{ "a": 1, "b": 2 }'})

open('sample.yaml')
format({'items:', '  - one', '  - two'})
vim.api.nvim_buf_set_lines(0, 0, -1, false, {'key: one', 'key: two'})
lint('yamllint', 'key-duplicates')
open('docker-compose.yml')
assert(vim.bo.filetype == 'yaml.docker-compose')
format({'services:', '  app:', '    image: alpine'})
vim.api.nvim_buf_set_lines(0, 0, -1, false, {'services: {}', 'services: {}'})
lint('yamllint', 'key-duplicates')

open('sample.toml')
format({'value = 1'})

open('sample.js')
format({'const value = { a: 1, b: 2 };'})

open('sample.ts')
format({'const value: number = 1;'})

open('sample.rs')
format({'fn main() {', '    println!("hi");', '}'})

open('sample.pl')
format({'my $value = { a => 1, b => 2 };'})
vim.api.nvim_buf_set_lines(0, 0, -1, false, {'use strict;', 'my $value = ;'})
language_error('perlnavigator')

open('project/sample.js')
assert(require('conform').list_formatters(0)[1].name == 'biome', 'Mason Biome fallback is missing')
format({'const value = { a: 1, b: 2 };'})
client('biome')
vim.api.nvim_buf_set_lines(0, 0, -1, false, {'if (1 == 2) { console.log("bad"); }'})
wait_until(function()
  for _, diagnostic in ipairs(vim.diagnostic.get(0)) do
    if tostring(diagnostic.code):find('noDoubleEquals', 1, true) then return true end
  end
  return false
end, 'Biome did not lint unsaved JavaScript')

open('sample.lua')
vim.api.nvim_buf_set_lines(0, 0, -1, false, {'local value = )'})
language_error('lua_ls')
open('sample.json')
vim.api.nvim_buf_set_lines(0, 0, -1, false, {'{"a": }'})
language_error('jsonls')
open('sample.toml')
vim.api.nvim_buf_set_lines(0, 0, -1, false, {'value = ['})
language_error('taplo')
open('rust/src/main.rs')
vim.api.nvim_buf_set_lines(0, 0, -1, false, {'fn main() { let _value: u32 = "wrong"; }'})
language_error('rust_analyzer')
open('sample.vim')
language_error('vimls')
open('Makefile')
lint('checkmake', 'uniquetargets')

for _, name in ipairs({'shell/.bashrc', 'shell/.bash_profile', 'x11/.xprofile', 'bin/bin/public-ip',
  'i3/.config/i3/scripts/keyhint-2', 'dav-mode/scripts/watch-pr/watch-pr'}) do
  open(name)
  local expected = name:find('watch-pr', 1, true) and 'typescript' or 'sh'
  assert(vim.bo.filetype == expected, name .. ' has incorrect filetype ' .. vim.bo.filetype)
  if expected == 'typescript' then
    format({'#!/usr/bin/env bun', 'const value: number = 1;'})
  end
end
open('project/dav-mode/scripts/watch-pr/watch-pr')
assert(vim.bo.filetype == 'typescript')
format({'#!/usr/bin/env bun', 'const value: number = 1;'})
open('bin/battery')
assert(vim.bo.filetype == 'perl', 'Extensionless Perl was not detected')

open('local/sample.md')
local local_info = require('conform').get_formatter_info('prettier', 0)
assert(local_info.command:find('/local/node_modules/.bin/prettier', 1, true), 'Project Prettier did not take precedence')
format({'- one', '    - two'})
assert(require('lint').linters['markdownlint-cli2'].cmd():find('/local/node_modules/.bin/markdownlint-cli2', 1, true),
  'Project Markdown linter did not take precedence')

open('failure/sample.md')
local failure
local complete = false
require('conform').format({async=true}, function(error) failure, complete = error, true end)
wait_until(function() return complete end, 'Failing formatter did not finish')
assert(failure, 'Project formatter failure was hidden by fallback')
assert(not vim.bo.modified, 'Failed formatter modified the buffer')

open('disabled/sample.js')
assert(#require('conform').list_formatters(0) == 0, 'Disabled Biome fell back to another formatter')
local before = vim.api.nvim_buf_get_lines(0, 0, -1, false)
require('conform').format({async=false})
assert(vim.deep_equal(vim.api.nvim_buf_get_lines(0, 0, -1, false), before))

open('unknown.custom')
assert(#require('conform').list_formatters(0) == 0, 'Unknown config received a generic formatter')
assert(vim.fn.getcwd() == vim.env.NVIM_TEST_ROOT, 'Linting changed the editor working directory')
vim.cmd.enew()
vim.bo.buftype = 'nofile'
vim.bo.filetype = 'markdown'
local special = vim.api.nvim_get_current_buf()
vim.api.nvim_feedkeys(vim.api.nvim_replace_termcodes(',cl', true, false, true), 'mx', false)
assert(#require('lint').get_running(special) == 0, 'Linter ran on a special buffer')
assert(not vim.o.autowrite and not vim.o.autowriteall and vim.o.clipboard == '')
vim.fn.writefile({vim.json.encode({formatting=true, linting=true, fallback=true, local_priority=true,
  disabled=true, unsaved=true, language_servers=true, extensionless=true, formatter_errors=true})}, vim.env.NVIM_TEST_REPORT)
vim.cmd('qa!')
"""

with tempfile.TemporaryDirectory(prefix="nvim-formatting-tests-") as temporary:
    root = Path(temporary).resolve()
    config_home = root / "config"
    config_home.mkdir()
    (config_home / "nvim").symlink_to(CONFIG, target_is_directory=True)
    (root / ".git").mkdir()
    (root / ".gitignore").write_text("node_modules/\n")
    files = {
        "notes.md": "# Heading\n\n* one\n* two\n",
        "sample.py": "value={'a':1,'b':2}\n",
        "sample.sh": "#!/bin/bash\nif true;then\necho hello\nfi\n",
        "sample.lua": "local value={a=1,b=2}\n",
        "sample.json": '{"a":1,"b":2}\n',
        "sample.yaml": "items:\n - one\n - two\n",
        "sample.toml": "value=1\n",
        "docker-compose.yml": "services:\n app:\n  image: alpine\n",
        "sample.js": "const value={a:1,b:2}\n",
        "sample.ts": "const value:number=1\n",
        "local/sample.md": "- one\n  - two\n",
        "disabled/sample.js": "const value={a:1}\n",
        "unknown.custom": "leave   this alone\n",
        "sample.rs": 'fn main(){println!("hi");}\n',
        "sample.pl": "my $value={a=>1,b=>2};\n",
        "sample.vim": "let g:value = )\n",
        "project/sample.js": "const value={a:1,b:2}\n",
        "project/control.js": "export const control = /[\\x00-\\x1f]/u;\n",
        "project/yuke/.config/yuke/plugins/control.js": "export const control = /[\\x00-\\x1f]/u;\n",
        "rust/src/main.rs": "fn main() {}\n",
        "Makefile": "all: clean test\n.PHONY: all clean test\nclean:\n\trm -f temporary\ntest:\n\techo okay\ntest:\n\techo duplicate\n",
        "shell/.bashrc": "#!/bin/bash\necho hello\n",
        "shell/.bash_profile": "echo hello\n",
        "x11/.xprofile": "echo hello\n",
        "bin/bin/public-ip": "echo hello\n",
        "i3/.config/i3/scripts/keyhint-2": "echo hello\n",
        "dav-mode/scripts/watch-pr/watch-pr": "#!/usr/bin/env bun\nconst value:number=1\n",
        "project/dav-mode/scripts/watch-pr/watch-pr": "#!/usr/bin/env bun\nconst value:number=1\n",
        "bin/battery": "#!/usr/bin/perl\nuse strict;\n",
        "failure/sample.md": "# Heading\n",
    }
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    (root / ".prettierrc.json").write_text(json.dumps({"tabWidth": 2, "proseWrap": "preserve"}))
    (root / ".yamllint").write_text("extends: relaxed\n")
    (root / ".markdownlint.json").write_text(json.dumps({"MD013": False, "MD041": False}))
    (root / "local/.prettierrc.json").write_text(json.dumps({"tabWidth": 4}))
    local_bin = root / "local/node_modules/.bin"
    local_bin.mkdir(parents=True)
    (local_bin / "prettier").symlink_to(Path.home() / ".local/share/nvim/personal/mason/bin/prettier")
    (local_bin / "markdownlint-cli2").symlink_to(Path.home() / ".local/share/nvim/personal/mason/bin/markdownlint-cli2")
    failure_bin = root / "failure/node_modules/.bin"
    failure_bin.mkdir(parents=True)
    failure_tool = failure_bin / "prettier"
    failure_tool.write_text("#!/bin/sh\necho 'fixture failure' >&2\nexit 1\n")
    failure_tool.chmod(0o755)
    (root / "project/biome.json").write_text((CONFIG.parents[2] / "biome.json").read_text())
    (root / "project/.git").mkdir()
    (root / "project/.gitignore").write_text("node_modules/\n")
    (root / "rust/Cargo.toml").write_text('[package]\nname="tooling-fixture"\nversion="0.1.0"\nedition="2024"\n')
    (root / "disabled/biome.json").write_text(json.dumps({"formatter": {"enabled": False}}))
    environment = dict(
        os.environ,
        XDG_CONFIG_HOME=str(config_home),
        XDG_STATE_HOME=str(root / "state"),
        XDG_CACHE_HOME=str(root / "cache"),
        NVIM_TEST_ROOT=str(root),
        CARGO_NET_OFFLINE="true",
    )
    for key in list(environment):
        if key.startswith("HERDR_") or key == "NVIM_APPNAME":
            environment.pop(key)
    try:
        biome = Path.home() / ".local/share/nvim/personal/mason/bin/biome"
        for name, expected in [("control.js", True), ("yuke/.config/yuke/plugins/control.js", False)]:
            check = subprocess.run(
                [str(biome), "lint", "--reporter=json", name],
                cwd=root / "project",
                text=True,
                capture_output=True,
                timeout=15,
            )
            diagnostics = json.loads(check.stdout)["diagnostics"]
            flagged = any(item["category"] == "lint/suspicious/noControlCharactersInRegex" for item in diagnostics)
            assert flagged == expected, f"Terminal regex exception has incorrect scope for {name}"
            assert check.returncode == (1 if expected else 0), check.stderr
        result = run_probe(CONFIG, root, environment, PROBE, timeout=120)
        result["terminal_regex_policy"] = True
    except Exception:
        evidence = Path(tempfile.mkdtemp(prefix="nvim-formatting-failure-")) / "fixture"
        shutil.copytree(root, evidence, symlinks=True)
        print(f"Failure evidence retained at {evidence}")
        raise
    for name, content in files.items():
        assert (root / name).read_text() == content, f"Tooling changed {name} on disk"
    print("Formatting checks passed:", result)
