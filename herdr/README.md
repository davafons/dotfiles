# Herdr on the Mac

The `mb` profile installs this package with GNU Stow.
`~/.config/herdr/config.toml` points to `.config/herdr/config.toml` in this package.
The `tower` profile uses the separate `herdr-tower` package.

Press `Ctrl+a`, release it, then press the action key.

| Action key | Action |
| --- | --- |
| `Ctrl+p` / `Ctrl+n` | Previous / next agent across workspaces |
| `Ctrl+1` through `Ctrl+9`, then `Ctrl+0` | Jump to agent 1 through 10 |
| `Ctrl+Alt+1` through `Ctrl+Alt+9`, then `Ctrl+Alt+0` | Jump to agent 11 through 20 |
| `w` | Open workspace navigation |
| `Shift+1` through `Shift+9`, then `Shift+0` | Jump to workspace 1 through 10 |
| `Shift+Alt+1` through `Shift+Alt+9`, then `Shift+Alt+0` | Jump to workspace 11 through 20 |
| `Shift+p` / `Shift+n` | Previous / next workspace |
| `Shift+c` | Create a workspace |
| `t` | Open the fuzzy navigator |
| `r` | Open checkout review beside this pane; from review, return to its source |
| `Shift+z` | Resize mode (moved from `r` to make room for review) |
| `g` | Create a jj workspace or Git worktree from `main` |
| `Shift+g` | Pick an existing jj workspace or Git worktree |
| `Shift+u` | Refresh checkout sidebar status |
| `h` / `j` / `k` / `l` | Focus the pane to the left / down / up / right |
| `p` / `n` | Previous / next tab |
| `1` through `9`, then `0` | Jump to tab 1 through 10 |
| `Alt+1` through `Alt+9`, then `Alt+0` | Jump to tab 11 through 20 in this workspace |
| `Shift+Tab` / `Tab` | Previous / next pane |
| `,` | Rename the current pane |
| `[` | Enter copy mode |
| `?` | Show the active keybindings |

The tenth workspace and agent sidebar entry shows `0`, matching its shortcut.
Tab badges retain the ordinal `10` for compatibility with the local status-color
patch. The local `sidebar-numbers` plugin supplies the three `0` bindings because
Herdr's built-in indexed bindings only accept `1..9`. It also supplies the second
bank, mirroring the first with Alt added: `Ctrl+a → Alt+5` jumps to tab 15,
`Ctrl+a → Ctrl+Alt+5` to agent 15, and `Ctrl+a → Shift+Alt+5` to workspace 15.
The `0` key selects item 20 in each second bank. Sidebar numbers 11–20 remain
ordinal numbers. Both banks follow the current resource order; tabs are scoped
to the invoking workspace, and missing positions leave focus unchanged.

Ctrl+Alt+digits require enhanced keyboard input (CSI-u/Kitty). Shift+Alt+6 also
requires it because its legacy `ESC ^` sequence starts an ANSI privacy message.
The workspace bindings include shifted-symbol aliases for other legacy inputs.

Verify the shortcut plugin and actual key dispatch without touching user panes:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s herdr/.config/herdr/local-plugins/sidebar-numbers -p 'test_*.py' -v
PYTHONDONTWRITEBYTECODE=1 python3 herdr/.config/herdr/local-plugins/sidebar-numbers/tests/check-shortcuts.py
```

The live check requires Herdr and tmux and uses a disposable named session with
20 workspaces, 20 tabs in the first workspace, and 20 reported test agents in a
detached terminal. It checks all 30 second-bank shortcuts with CSI-u, supported
legacy Alt inputs, all three `0` shortcuts, and missing positions in each bank.

Direct `Ctrl+h`, `Ctrl+j`, `Ctrl+k`, `Ctrl+l`, `Ctrl+p`, and `Ctrl+n` pass through
to the application. Use `Ctrl+a`, then `h/j/k/l`, for Herdr pane navigation.
The old global Ctrl+j action swallowed the key even when no pane existed below,
preventing Yuke from receiving its newline/history/panel shortcuts. Direct
intercepts are now removed. The local navigator also recognizes Yuke and forwards
these keys if an already-loaded client or manual action still invokes it.

New tabs open immediately with generated names. Tabs containing detected agents
group their global shortcut number and default status dot in one badge before
the tab name, for example `[3 ●] 2`. Multiple agents use `[2,3 ●] tab-name` with
the tab's combined status. Terminal-only tabs keep their ordinary name. Brackets
are muted gray, numbers retain the normal foreground, and the local Herdr client
patch colors only the dot using the sidebar status palette: working yellow,
blocked red, done teal, idle green, and unknown muted gray. Titles retain their
normal foreground and active-tab background. Coloring requires the patched
client binary; detach and reattach after installing it, without stopping the
server or agents. A normal `herdr update` can replace this local binary patch.

Copy mode uses Vim movement keys. Press `v` to start a selection.
Press `y` to copy it. Press `/` to search. Press `q` to leave.

Install [Herdr Navigator](https://github.com/thanhdat77/herdr-navigator) on a new machine:

```sh
herdr plugin install thanhdat77/herdr-navigator --ref v0.3.6 --yes
herdr config check
herdr server reload-config
```

The plugin requires a Rust toolchain for its build. Stow installs the config.
The command above installs the plugin. Plugin build files and runtime state stay
outside this package.

## jj workspaces and Git worktrees

The local `david.workspaces` plugin detects the repository of the invoking pane.
Colocated repositories and linked jj workspaces always use jj; Git-only repos use
Herdr's native `worktree.create/list/open` APIs. The Git-only default creation key
is replaced by the jj-aware actions above. No checkout is deleted automatically.

The create popup asks for a workspace/branch name. Both backends start on `main`
and fail clearly if it does not exist. jj also asks for an optional checkout path;
the default is `~/.herdr/jj-workspaces/<project>-<id>/<name>`. It refuses existing
names and destinations. If checkout creation succeeds but Herdr opening fails,
the checkout is preserved and can be opened again with `Shift+g`.

The fuzzy picker marks the invoking pane's checkout with `*`, shows checkout
names and full paths, and reuses an already-open jj pane instead of duplicating
it. Type to filter, Enter to open, or Escape to cancel. Ctrl-C cancels creation.
Workspace/machine rows show only their shortcut number and label, with no
checkout, description, or status indicator. Agent entries show their own pane's
actual checkout rather than inferring it from a manually assigned Herdr label.
The bare checkout name sits beside the project on the same header line, for
example `shirabe · default`, with no `jj /` or `git /` prefix or separate checkout
row. The default status dot and purple change ID/branch share that header too;
Herdr ellipsizes long labels to fit. Project labels are blue and checkout names
cyan. File counts and clean/empty status are not displayed. The second row shows
Codex terminal titles or Yuke session summaries in the same explicit dark gray,
without stacking terminal faint. Workspace/machine rows remain labels only.

Status refreshes on focus, pane, worktree, and agent-state events. On macOS, a
per-session launchd job also refreshes every 15 seconds, picking up changes in
pane cwd and repository state without opening a terminal or switching focus.
The job is a periodic one-shot command, not an unsupervised plugin daemon.
Metadata expires after 60 seconds if the refresher stops, and the job stops
publishing if the plugin is disabled or unlinked. Linux uses event/manual
refreshes only (no launchd installation or expiring heartbeat).

**jj background reads deliberately do not snapshot or merge operations.** File
counts, descriptions, and conflicts reflect the saved `@` change from the last
jj command; edits not yet snapshotted are not included. Run `jj status` to
snapshot them normally, then refresh if needed. No background Git commands run
in jj checkouts, and no push/staging/signing configuration is changed. Only the
plugin's `jj workspace add` command disables signing for its new automated change.

On a new machine, Stow installs the sources/config; link and enable the plugin:

```sh
herdr plugin link "$HOME/.config/herdr/local-plugins/workspaces" --enabled
herdr plugin action invoke david.workspaces.install-refresh  # macOS, current session
herdr plugin action invoke david.workspaces.refresh
herdr config check
herdr server reload-config
```

Requires Python 3.9+, jj 0.40+ for the jj template/root APIs, Git, and `fzf` for
the picker. Startup restores metadata and registers automatic refresh for new
macOS sessions. Linking into an already-running session requires the explicit
`install-refresh` invocation above. To remove a session's timer:

```sh
herdr plugin action invoke david.workspaces.uninstall-refresh
```

Timers live under `~/Library/LaunchAgents/dev.herdr.workspaces.<session-id>.plist`;
locks and refresher logs live in the plugin's Herdr-managed state directory, not
in this repository. To disable the integration, uninstall its timer, disable the
plugin, and remove its key/sidebar configuration. Startup reinstalls a removed
timer while the plugin remains enabled.

Run the isolated repository tests without touching user history or GUI focus:

```sh
cd "$HOME/.config/herdr/local-plugins/workspaces"
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v test_workspaces
```

Validated with Herdr 0.9.3 and jj 0.40.0: 17 tests, live jj creation/open/reuse
and metadata, actual create and fzf picker popups in a private PTY-backed test
session, native Git worktree creation/opening with dirty checkout metadata, and
successful periodic launchd refreshes. No desktop window was opened or activated.

Navigation/color regression checks:

```sh
cargo test --manifest-path "$HOME/.config/herdr/local-plugins/nvim-navigation/Cargo.toml"
python3 "$HOME/.config/herdr/local-plugins/nvim-navigation/tests/check-herdr-navigation.py"
# Also verify top-tab dot colors and number-first spacing with the patched client:
HERDR_TEST_TAB_STATUS_COLORS=1 python3 "$HOME/.config/herdr/local-plugins/nvim-navigation/tests/check-herdr-navigation.py"
```

The second check needs `tmux`, a C compiler, and the linked local plugins. It
creates a named Herdr test session and detached tmux terminal, runs a raw-input
fixture named `yuke` (no model access), and proves legacy/enhanced Ctrl+j and
Ctrl+h/k/l delivery even with a neighboring Herdr pane. It also checks prefixed
pane movement, the navigator's Yuke passthrough, inline checkout truncation, and
rendered blue/cyan/purple/red ANSI styles. Eight Rust tests pass; the live check
saves a text artifact and removes its test session and timer on exit.

After a config edit, run `herdr config check`, then `herdr server reload-config`.
If an attached client retains its old keys, press `Ctrl+a`, then `Shift+r` to
reload its local config.

## Neovim checkout review

The local `david.review` plugin opens a persistent Neovim split beside the
invoking pane, using that pane's actual checkout. Wide panes split right;
narrow ones split down. CodeDiff starts inline below 100 editor columns,
otherwise side by side; `t` changes the layout inside the diff.

Press `Ctrl+a`, then `r`, from an agent pane to open review. Press it from
the review pane to return. `,ab` or `:HerdrReviewReturn` also returns to the
source pane. Closing the CodeDiff tab with `q` returns automatically. The
editor remains alive, retaining buffers, unsaved edits and queued annotations;
opening review again focuses that editor and reopens its diff if needed.
Each source pane/checkout has its own review editor.

jj checkouts compare the working tree against `@-`; Git-only checkouts compare
against `HEAD`. The jj query snapshots current work normally when review is
requested. CodeDiff currently needs `.git` in the checkout; non-colocated jj
workspaces are refused. This is a checkout review and includes other agents'
or manual edits in the same checkout. Checkpoints and agent-only attribution
are deferred.

The Neovim adapter is `config.herdr_review` in the personal nvim package. It
targets questions and queued comments at the invoking agent. Use `gf` to open
the real file, `,aa` to annotate, `,ap` to preview and `,aS` to submit. Leaving
review does not send anything. `,at` explicitly chooses another comment target;
it also accepts a replacement session in the same source pane. If that agent
has gone or its reported session changed, sending is refused and comments are retained.
Transcript-based edit marks still depend on upstream agent support.

On a new machine after Stow has linked the package:

```sh
herdr plugin link "$HOME/.config/herdr/local-plugins/review"
herdr config check
herdr server reload-config
```

The action is also available as
`herdr plugin action invoke toggle --plugin david.review` inside Herdr.
In a review editor, `:HerdrReviewOpen` reopens its current-change view.
Run its real integration check without touching live panes or sending prompts:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 "$HOME/.config/herdr/local-plugins/review/tests/check-review.py"
```

The check uses a private Herdr session, a detached tmux terminal and a temporary
jj repository. It tests rendering, pane reuse, returning with unsaved edits,
distinct source panes and annotation routing through a capture executable.

See the [keyboard guide](https://herdr.dev/docs/keyboard/) for the built-in keys.
