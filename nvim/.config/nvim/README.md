# Personal Neovim configuration

Standalone Neovim with lazy.nvim, Solarized, nvim-tree, fzf-lua, Treesitter, native LSP, blink.cmp, Rails navigation and jj/Herdr review tools.

AI assistance and tests run in Herdr. Plugins, parsers and Mason tools are installed separately under ~/.local/share/nvim/personal, preserving the previous LazyVim runtime. Versions are pinned in the plugin specs and lazy-lock.json.

## Personal defaults

Comma leader; two-space indentation; relative numbers; displayed-line j/k, including counts; screen wrapping; textwidth 99 and a column-100 guide. Saving and clipboard copying are explicit. No formatting on save. Undo history persists with 10,000 levels. Whitespace markers, a global status line and save/discard/cancel confirmation are enabled. Ctrl-C and H/L retain native behavior. No custom split creation or Alt mappings.

The statusline shows formatter availability and language servers attached to the
current buffer, for example `fmt:prettier` and `lsp:marksman`. `fmt:none` means no
formatter is configured for a normal file buffer. Special buffers also show none.
`(missing)` means its executable is absent. `(no-root)` means required project
configuration is absent, and `(unavailable)` means its
condition failed, including disabled or unsupported Biome formatting. Biome
availability is checked asynchronously and shows `(checking)` while pending.
Statusline redraws use cached formatter results rather than starting tools.
Buffer switches, filetype or filename changes, saves, directory changes, and
regained focus refresh the cache.
`lsp:none` means no server is attached. Configured but inactive servers are not
listed. LSP progress symbols come from lualine's existing component.

## Shortcuts

Starting nvim without a file opens the Snacks dashboard, the same dashboard plugin used by LazyVim. Its keys are f (find files), n (new file), g (search text), r (recent files), p (recent projects), c (configuration), s (restore session), l (plugins), ? (Vim shortcuts), and q (quit). The homepage also shows a compact learning reminder. File/project choices use fzf-lua. Projects come from recently opened files in jj or Git repositories; choosing one changes directory and opens its file picker. Session restoration stays explicit.

Open the full [Vim field guide](doc/shortcuts.md) with ,h or :VimShortcuts from anywhere. It opens a read-only tab: / searches the guide, n/N move between matches, and q returns to your previous tab. It covers custom mappings, native motions, operators and text objects, registers, macros, splits, LSP, Rails and the Herdr review loop. Learn operator + motion first, then counts and the repeat command (.).

| Keys | Action |
| --- | --- |
| Ctrl-h/j/k/l | Navigate Neovim splits and adjacent Herdr panes |
| Ctrl-w s / Ctrl-w v | Native horizontal / vertical split |
| ,y / ,Y | Copy selection or line to system clipboard |
| ,Esc / ,bd | Clear search highlights / delete buffer |
| ,p in visual mode | Replace selection while retaining the yank register |
| ,e | Toggle nvim-tree |
| ,E | Reveal the current file in nvim-tree and focus it |
| ,Space / ,ff / ,tt | Find files using the current file's project root |
| ,/ / ,sg / ,tg | Search text using the current file's project root |
| ,tb / ,tr / ,tp | Open buffers / recent files / recent projects |
| ,h / :VimShortcuts | Searchable Vim shortcut guide |
| gd / gr / K | Definition / references / documentation |
| ,ts / ,tS | File / project symbols |
| ,df / ,xx / ,xX | Line / project / buffer diagnostics |
| ,jd / ,jf / ,jm | JJ change / file against parent / changes since main |
| ,jl / ,js | JJ log / status |
| ,ac / ,ar / ,at | Ask about code / follow up / choose Herdr agent |
| ,aa / ,al / ,ap / ,aS | Queue / list / preview / send review comments |
| ]r / [r / ,ak | Next / previous tracked agent edit / mark reviewed |
| ,cf / ,cl | Format explicitly / run linters |
| ,ra / ,rr | Rails alternate / related file |
| ,rm / ,rc / ,rv | Rails model / controller / view lookup |
| sa / sd / sr | Add / delete / replace surrounding text |
| gcc / gc | Native comment line / selection |
| ]m / [m / af / if | Next / previous function / outer / inner function text |
| ,qs / ,qS / ,ql / ,qd | Restore / choose / last session / stop session saving |
| ,mp | Toggle Markview rendering for this Markdown buffer |
| ,ms | Toggle the live Markdown preview split |
| ,mv | Preview the saved Markdown file with mcat in a native Ghostty split |
| ,tT / ,xt | Find TODOs / TODO diagnostic list |
| ,? | Show buffer keybindings |

Markdown uses Markview with screen wrapping and hybrid editing: the current line
stays raw in normal and insert mode while surrounding lines render. ,ms opens a
preview to the right, follows unsaved edits, and keeps focus in the source. Press
,ms again to close it. Native gx remains unchanged.
Markdown accents match Yuke's Solarized theme in dark and light mode. Headings
and bullets are blue, bold text is brighter, inline code is yellow, and quotes
are green. Headings have no icons, gutter signs, or background bands. Inline
code has no background or extra padding. The editor's base Solarized colors and
syntax highlighting inside fenced code blocks remain unchanged.

For proportional-font reading, save with :w and press ,mv (or run :McatPreview).
It launches `mcat -I --kitty` in a native Ghostty split to the right, including
when Neovim runs inside Herdr. Ghostty must be the active app. The preview reads
the saved file and starts in its directory; it never saves your buffer. Quit mcat
with q, then save and launch again to refresh.
Each launch opens a new split. Use ,ms instead for live previews of unsaved edits.
This requires macOS, Ghostty 1.3+ with AppleScript enabled, and mcat on Neovim's
PATH (`brew install mcat`). Allow control of Ghostty if macOS asks. Launch errors
appear as Neovim warnings. In the mcat 0.6.5 desktop-free PNG check, text rendered
but a relative local image did not; this launcher does not rewrite image links.

:Mason is available at startup and manages the selected language servers. :InstallTools installs the selected standalone formatting/linting tools. Neovim's native LSP uses vim.lsp.config/vim.lsp.enable, with nvim-lspconfig supplying server definitions and mason-lspconfig installing/enabling them.

Formatting is explicit and follows repository tooling. Ruby uses project Bundler
and its RuboCop rules. Biome and Prettier prefer project-local executables and
fall back to installed Mason tools. A biome.json/biome.jsonc selects Biome, which
determines whether formatting is enabled for the file. Unsupported or disabled
formats do not fall back to another formatter. ERB uses the local Herb formatter
with .herb.yml. No LSP formatting fallback or automatic fixes on save are enabled.

Markdown uses Markdownlint CLI2, YAML uses yamllint, and saved Makefiles use
Checkmake. Standalone linters find configuration from the file's directory;
stdin-capable linters include unsaved edits. Rust adds rustfmt and rust-analyzer.
Perl adds native PerlTidy and PerlNavigator syntax checking. Vimscript uses the
Vim language server. The [dotfiles tooling guide](../../../TOOLING.md) covers
repository defaults, dependencies, and formats without safe generic tooling.

| Project/files | Navigation and diagnostics | Explicit formatting |
| --- | --- | --- |
| Shirabe Ruby/Rails | Ruby LSP with project RuboCop diagnostics; vim-rails | Bundled RuboCop, including Rails Omakase rules |
| Shirabe HTML/ERB | Herb LSP plus Ruby LSP | Project Herb formatter |
| Shirabe JavaScript/JSON | vtsls / JSON LSP plus project Biome | Project Biome |
| Shirabe Markdown/YAML | Marksman / YAML LSP | Project Prettier |
| Nadeshiko TypeScript | vtsls plus project Biome | Project Biome |
| Nadeshiko Vue | Vue LSP, vtsls, Biome and Tailwind | Disabled by the repository's Biome setup |

vtsls prefers each workspace's TypeScript SDK and enables the Vue plugin with it. Biome and Herb start in their project directories even when Neovim was launched elsewhere. Java/Kotlin use the installed Homebrew Java 21 runtime when JAVA_HOME is unset. Other language tooling remains configured through lua/config/languages.lua and lua/config/tools.lua.

:ConformInfo shows formatter availability for the current file; :checkhealth vim.lsp shows language-server status. Diagnostics come from language servers and nvim-lint; Treesitter handles syntax highlighting, folding and text objects, with Solarized supplying colors. Mason installs tools; it does not itself run formatting or lint checks.

CodeDiff/jj review supports Git-backed jj repositories. Git staging/discard maps and jj.nvim push shortcuts are disabled; use the checked jj push alias in Herdr.

File and text search resolve the nearest jj or Git root from the current regular file, falling back to the working directory in special buffers or outside a repository. Search leaves the working directory unchanged. Dashboard searches use the same policy, with the configuration button explicitly searching this config.

CodeDiff is the visual old/new code viewer used by ,jd (current jj change), ,jf (current file against its parent) and ,jm (current work against main). Reviews start inline with the changed-file list hidden. ,b shows or hides the list; ]f/[f navigate files without it. ]c/[c navigate hunks, t switches to side-by-side, gc folds unchanged code, gf opens the real file for inspection or annotations, g? shows help and q closes the diff tab. Repository diffs include everyone's work; they are not an agent attribution mechanism.

In Herdr, Ctrl-a then r opens checkout changes in the full shared Code tab through the local david.code plugin. Ctrl-a e or ,ab returns to the source pane. ,ad switches between files and changes; q closes the diff to files without leaving Code. Buffers, unsaved edits and queued comments survive view changes. ,as asks for a recipient before sending tagged code; ,at chooses the default for questions. Each worktree keeps its own editor and recipient.

The older david.review.toggle action still opens a per-agent split without a shortcut. Its dedicated adapter, lua/config/herdr_review.lua, uses the same diff defaults. In that legacy editor, ,ab / :HerdrReviewReturn and q return to the source pane. Questions and batch comments target the invoking agent; ,at selects another target or accepts a replacement session. No messages are sent just by opening or leaving either review. See [the review design](doc/herdr-review-proposal.md) for deferred checkpoints and agent attribution.

## Completion

blink.cmp automatically shows command and argument candidates while typing :,
including file paths for :edit. Tab / Shift-Tab or Up / Down select and preview
candidates; Ctrl-y accepts, Enter executes the command, and Esc cancels. Nothing
is preselected. Left / Right still move through the command text; Ctrl-n/p remain
available to Herdr. Search prompts (/ and ?) do not automatically open the menu;
Tab requests completion when needed. Noice displays : in a floating command box
with inline ghost-text suggestions. Search prompts stay at the bottom.

Function-parameter help appears automatically while typing calls when the language
server supports it. Blink owns automatic signatures; Noice does not add a second
signature provider. The existing gs and K shortcuts still provide native LSP help.

Snacks highlights references to the symbol under the cursor when the language
server supports document highlights. The [[ and ]] class-navigation keys are
unchanged. Snacks also detects files over 1.5 MiB or with average lines over 1,000
characters. These use the bigfile filetype, which skips language servers,
Treesitter highlighting, automatic completion, and expression folding.

## Shortcut changes

Restored LazyVim's ,Space / ,ff file picker and ,/ / ,sg text search shortcuts.
The existing ,tt / ,tg mappings remain aliases. Clear search highlights moved
from ,Space to ,Esc.

Enabled blink.cmp command-line completion on CmdlineEnter, including automatic
candidate menus for : commands without requiring insert mode first.

Enabled Noice's floating command UI and ghost text, Blink automatic signatures,
Snacks reference highlighting, and large-file protection. grug-far remains absent.

Replaced render-markdown.nvim with Markview. ,mp now toggles the current buffer;
,ms toggles its live preview split. The old renderer's Solarized highlight
customizations were removed. Added ,mv and :McatPreview for saved-file mcat
previews in a native Ghostty split, without automatic saves.
Matched Markdown accents to Yuke's Solarized palette and replaced decorative
headings and list markers with plain headings and bullets.

## Backup and validation

Migration backups remain local and are not included in this repository.

Run `python3 -B tests/check-config.py` after installing the pinned plugins. The
check starts Neovim in an invisible terminal with temporary state and cache
directories. It checks startup, editor defaults, command completion, review
dependencies, project roots, pickers, the shortcut guide, and unsaved edits.
No desktop or clipboard input is used.

Run `python3 -B tests/check-statusline.py` for the drawn formatter/LSP badges,
missing tools and roots, unavailable and pending conditions, attached-only
servers, buffer switches, stale async results, cached redraws, and unsaved edits.
It retains its private terminal fixture and screen capture outside the checkout.

Run `python3 -B tests/check-enhancements.py` for large/minified-file protection,
Noice's floating command box and ghost text, reference highlights, and automatic
signature help from the installed Lua language server.

Run `python3 -B tests/check-diff.py` for inline/full-width review, the hidden
file list, layout and list toggles, file/hunk navigation, unchanged-code folding,
and unsaved buffers. These checks require an explicit completion report rather
than trusting the editor's exit status.

Run `python3 -B tests/check-formatting.py` for real mapped formatting and linter
and language-server diagnostics. It checks Mason fallback, local-tool priority,
disabled formats, formatter errors, extensionless scripts, unsaved edits, and
unchanged files on disk. It uses a private terminal and retains failure fixtures.

Run `python3 -B tests/check-markdown.py` for Markview rendering, hybrid editing,
toggle and live preview checks. It tests dark and light Markdown colors,
colorscheme reloads, plain headings and bullets, inline code padding, focus,
unsaved edits, preview additions and deletions, and the unchanged file on disk.

Run `python3 -B tests/check-mcat.py` for the mcat shortcut and command, path quoting,
working directory, explicit-save guards, launch errors, and duplicate-launch
protection. It uses stub executables at the Ghostty boundary and sends no Apple
events. It does not verify the native split or graphics display.

Validated with Neovim 0.12.1: actual pinned plugin installs, 28 parsers, Rust blink and CodeDiff native libraries, startup in a background terminal, Ruby symbols, Vue/TypeScript and Lua definitions, Vue/Svelte comments, Rails file navigation, watched reload preserving unsaved edits, and explicit formatting. Actual Shirabe/Nadeshiko checks also pass from outside either project: Ruby/RuboCop, Biome and Herb diagnostics, repository formatting rules, Vue definition navigation, disabled Vue formatting and disabled Herb fixes on save. The dashboard was checked in background terminals: empty startup, all menu keys, real fzf project selection, explicit session behavior, restored status line and direct file startup. All 33 selected Mason packages are installed. Other language tools are configured but have not been checked against real projects. Herdr companion actions are registered and its configuration reloads cleanly. Live pane navigation and sending agent prompts were not exercised.
