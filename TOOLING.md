# Dotfiles formatting and linting

## Editor commands

Use `,cf` to format the current buffer or visual selection. Formatting changes
only the buffer. Saving remains explicit. There is no format-on-save or automatic
lint fixing.

Use `,cl` to run standalone linters. They also run when a file opens and after a
save. Language servers provide additional diagnostics while editing. `,df` shows
line diagnostics, `,xX` lists buffer diagnostics, and `,xx` lists project
diagnostics. `:ConformInfo` shows the selected formatter.

Project-local Node tools and bundled Ruby tools take precedence. Mason tools are
fallbacks when no local executable exists. A disabled or unsupported Biome format
does not fall back to Prettier. A failing selected formatter reports its error
rather than trying another version.

Standalone linters run from the file's directory so they find its project
configuration even when Neovim starts elsewhere. Markdownlint also prefers a
project-local executable. ShellCheck, Ruff, Markdownlint, and yamllint read the
current buffer, including unsaved changes. Checkmake reads saved files and does
not run against modified buffers. Special buffers are not linted.

## Tools for this repository

| Files | Explicit formatter | Diagnostics |
| --- | --- | --- |
| Markdown | Prettier | Markdownlint CLI2 and Marksman |
| Python, including shebang scripts | Ruff | Ruff and Pyright |
| JavaScript, TypeScript, MJS, JSON, JSONC | Biome | Biome and the relevant language server |
| YAML, including Compose YAML | Prettier | yamllint and YAML/Compose language servers |
| TOML | Taplo | Taplo |
| Lua | StyLua | Lua language server |
| Bash/POSIX shell, including recognized extensionless scripts | shfmt | ShellCheck and Bash language server |
| Rust | rustfmt | rust-analyzer |
| Perl shebang scripts | PerlTidy | PerlNavigator syntax checking |
| Brewfile/Ruby | RuboCop | Ruby language server |
| Makefiles | Native indentation only | Checkmake on saved files |
| Vimscript | Native indentation only | Vim language server syntax diagnostics |

Use native `=` indentation for Makefiles and Vimscript. Make recipes retain their
required tabs. Included `.mk` fragments are not complete Makefiles; Checkmake's
whole-file target rules may not apply to them. The repository's existing
`make check` remains its behavioral test command, not a replacement for all
language linters.

Mason does not manage every runtime dependency. `rustfmt` comes from the Rust
toolchain. PerlTidy comes from Homebrew's `perltidy` formula on macOS or
`perl-tidy` on Arch. These are listed in the package manifests. Perl::Critic is
not installed or enabled; Perl coverage is syntax checking, not a Perl style
policy. Vim language server is used instead of Vint because the current Mason
Vint package failed to start in this environment.

## Repository defaults

The root configurations define the defaults without adding a Node dependency
installation solely for editor tools.

| Configuration | Purpose |
| --- | --- |
| `biome.json` | Two-space JS/TS/JSON formatting, recommended lint rules, terminal-control regex exception for Yuke plugins, Git-ignore awareness, no automatic assists |
| `.prettierrc.json` | Two-space indentation, width 99, preserve prose wrapping |
| `.markdownlint.jsonc` | Standard Markdown rules without hard prose line limits, HTML restrictions, or mandatory opening headings |
| `.yamllint` | Relaxed YAML style with duplicate-key and syntax checks |
| `ruff.toml` | Python correctness rules, Python 3.12 target, width 120, extensionless Python entries |
| `.stylua.toml` | Two-space Lua formatting and width 120; nested configuration still takes precedence |
| `checkmake.ini` | Required `all`/`check` phony targets and a recipe-length limit suitable for this Makefile |

Linters can report existing issues in older scripts or imported upstream files.
Adding these tools does not imply that all existing files are lint-clean. No
repository-wide reformatting is performed automatically.

## App-specific configuration

Ghostty, tmux, i3, Hyprland, SSH, Git configuration, INI variants, Xresources, and
package lists do not share one safe formatter or one validation grammar. They
are intentionally not routed through a generic formatter. Use each application's
own validation where available. Linux-only application validation has not been
proved on this Mac. License files, TSV logs, lockfiles, and arbitrary text are
not treated as source code merely to give them a formatter.

## Install and verify

Run `:InstallTools` for the selected Mason formatting/linting packages. Language
servers are managed by mason-lspconfig. Install the native dependencies using the
platform package manifest. Restart Neovim after changing the configuration.

Run the editor behavior checks from the repository root:

```sh
python3 -B nvim/.config/nvim/tests/check-formatting.py
python3 -B nvim/.config/nvim/tests/check-config.py
python3 -B nvim/.config/nvim/tests/check-markdown.py
make check
```

The formatting check uses actual installed tools in a private terminal. It
checks mapped formatting, standalone and language-server diagnostics, local
priority, fallback, disabled formatting, errors, extensionless filetypes, and
unchanged source files on disk. It requires PerlTidy, rustfmt, the selected Mason
tools and servers, and the installed plugins/parsers. Failure fixtures and logs
are retained outside the checkout. The check never attaches to an open editor.
