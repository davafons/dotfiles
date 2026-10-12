# Herdr on the Mac

The `mb` profile installs this package with GNU Stow.
`~/.config/herdr/config.toml` points to `.config/herdr/config.toml` in this package.
The `tower` profile uses the separate `herdr-tower` package.

Press `Ctrl+a`, release it, then press the action key.

| Action key | Action |
| --- | --- |
| `Ctrl+p` / `Ctrl+n` | Previous / next agent across workspaces |
| `Ctrl+1` through `Ctrl+9`, then `Ctrl+0` | Jump to agent 1 through 10 |
| `Ctrl+Shift+F1` through `Ctrl+Shift+F10` | Jump to agent 11 through 20 |
| `w` | Open workspace navigation |
| `Shift+1` through `Shift+9`, then `Shift+0` | Jump to workspace 1 through 10 |
| `Shift+F1` through `Shift+F10` | Jump to workspace 11 through 20 |
| `Shift+p` / `Shift+n` | Previous / next workspace |
| `Shift+c` | Create a workspace |
| `t` | Open the fuzzy navigator |
| `e` | Open this checkout's shared Code tab; from Code, return to the last source pane |
| `Shift+e` | Open the same editor in a quick overlay |
| `r` | Open checkout changes in the full shared Code tab |
| `Ctrl+e` | Edit terminal scrollback (moved from `e`) |
| `Shift+z` | Resize mode (moved from `r` to make room for review) |
| `g` | Create a jj workspace or Git worktree from `main` |
| `Shift+g` | Pick an existing jj workspace or Git worktree |
| `Shift+u` | Refresh checkout sidebar status |
| `h` / `j` / `k` / `l` | Focus the pane to the left / down / up / right |
| `p` / `n` | Previous / next tab |
| `1` through `9`, then `0` | Jump to tab 1 through 10 |
| `F1` through `F10` | Jump to tab 11 through 20 in this workspace |
| `Shift+Tab` / `Tab` | Previous / next pane |
| `,` | Rename the current pane |
| `[` | Enter copy mode |
| `?` | Show the active keybindings |

The tenth workspace and agent sidebar entry shows `0`, matching its shortcut.
Tab badges retain the ordinal `10` for compatibility with the local status-color
patch. The local `sidebar-numbers` plugin supplies the three `0` bindings because
Herdr's built-in indexed bindings only accept `1..9`. For items 11–20, the plugin
uses function keys: `Ctrl+a → F5` jumps to tab 15, `Ctrl+a → Ctrl+Shift+F5` to
agent 15, and `Ctrl+a → Shift+F5` to workspace 15. F10 selects item 20.
Sidebar numbers 11–20 remain ordinal numbers. Both banks follow the current
resource order; tabs are scoped to the invoking workspace, and missing
positions leave focus unchanged.

No configured Herdr shortcut requires Alt/Option. The function-key banks accept
standard terminal sequences and CSI-u/Kitty input. On Mac, function keys may
require Fn if the top row controls media or brightness. macOS can also reserve
modified function keys; `Ctrl+a t` remains available to find any item.

Verify the shortcut plugin and actual key dispatch without touching user panes:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s herdr/.config/herdr/local-plugins/sidebar-numbers -p 'test_*.py' -v
PYTHONDONTWRITEBYTECODE=1 python3 herdr/.config/herdr/local-plugins/sidebar-numbers/tests/check-shortcuts.py
```

The live check requires Herdr and tmux and uses a disposable named session with
20 workspaces, 20 tabs in the first workspace, and 20 reported test agents in a
detached terminal. It checks all 30 function-key shortcuts with SS3/CSI,
CSI-tilde and CSI-u input, the unchanged 1–10 banks, and missing positions in
each bank. A capture executable verifies the scrollback shortcut launches
`$EDITOR` with the focused pane's text and cleans up its temporary file.
No desktop input or real editor launch is used.

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

Status refreshes at startup and on focus, pane, worktree, and agent-state events
on both macOS and Linux. Press `Ctrl+a`, then `Shift+u`, to refresh manually after
repository edits while staying in the same pane. Metadata remains until the next
refresh or until the pane/workspace closes; it no longer expires after 60 seconds.

**jj background reads deliberately do not snapshot or merge operations.** File
counts, descriptions, and conflicts reflect the saved `@` change from the last
jj command; edits not yet snapshotted are not included. Run `jj status` to
snapshot them normally, then refresh if needed. No background Git commands run
in jj checkouts, and no push/staging/signing configuration is changed. Only the
plugin's `jj workspace add` command disables signing for its new automated change.

On a new machine, Stow installs the sources/config; link and enable the plugin:

```sh
herdr plugin link "$HOME/.config/herdr/local-plugins/workspaces" --enabled
herdr plugin action invoke david.workspaces.refresh
herdr config check
herdr server reload-config
```

Requires Python 3.9+, jj 0.40+ for the jj template/root APIs, Git, and `fzf` for
the picker. Startup restores metadata. After linking into a running session, use
the explicit `refresh` invocation above. Locks live in Herdr's plugin state
directory, not in this repository.

### Background activity notifications (0.1.1)

The workspace plugin no longer installs per-session macOS LaunchAgents. Those
jobs caused macOS to announce that Python could run in the background, including
for temporary test sessions. Event/manual refresh replaces the 15-second timer;
creating, opening, and inspecting jj workspaces or Git worktrees is unchanged.

For a session with an old timer, remove it with:

```sh
herdr plugin action invoke david.workspaces.uninstall-refresh
```

This removes only that session's `dev.herdr.workspaces.<session-id>.plist` job.
It does not disable Python, other background services, or the workspace plugin.
To disable the integration itself, disable the plugin and remove its key/sidebar
configuration.

Run the isolated repository tests without touching user history or GUI focus:

```sh
cd "$HOME/.config/herdr/local-plugins/workspaces"
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v test_workspaces
```

The test suite requires Python 3.11+ and covers read-only jj status, creation
from `main`, existing-checkout reuse, Git-only fallback, event metadata, and
startup without background-job registration. Repository tests run in temporary
checkouts and do not open desktop windows.

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

## Workspace Code tab and overlay

Press `Ctrl+a`, then `e`, from a pane in a checkout. The local `david.code`
plugin opens a `Code · <checkout>` tab inside the current Herdr workspace.
Press the same shortcut from Code to return to the pane you came from. Opening
from another agent in the same checkout reuses the editor and updates the return
destination, not the message recipient. Each worktree gets its own editor,
buffers, queued tags and recipient. The key includes the canonical checkout
path, Herdr workspace ID and Herdr session socket; another workspace or session
gets a separate editor even for the same checkout. Workspace labels are not used
to infer paths.

Code tabs stay in the leftmost group of the top tab bar. Opening or selecting a
worktree's Code tab brings it first; other Code tabs follow in recent-use order.
Moving an ordinary tab ahead of that group, or dragging a Code tab away, restores
the pinned group without changing pane focus or the ordinary tabs' relative order.
An ordinary tab named Code is not pinned. To restore existing tabs after linking
an update, invoke `herdr plugin action invoke david.code.pin`.

The Code host pane, quick overlay and Neovim all start in the invoking pane's
canonical checkout root, including when invoked from a nested directory. The
launcher resolves its script from the plugin directory, not from the checkout.
No Herdr core modification or workspace-name override is needed. Herdr keeps its
normal first-tab naming: a single-checkout workspace retains its checkout name;
with several checkouts, its automatic name can follow the leftmost Code tab's
checkout. Explicit workspace names remain unchanged.

`Ctrl+a`, then `Shift+e`, opens that editor in a large terminal overlay above the
source pane. The tab and overlay share buffers, cursor positions, undo history,
LSP state and queued comments. Only one Neovim UI attaches at a time. In normal
mode, `,ab` returns and dismisses the overlay; `,ae` promotes it to the full Code
tab. `Ctrl+a e` or `Ctrl+a Shift+e` also dismisses the overlay in normal mode.
Escape keeps its normal Vim meaning. Popups receive all terminal input, so leave
insert mode before using these normal-mode shortcuts.

The editor opens with the checkout's existing file tree. The main Vim controls
are:

| Keys | Action |
| --- | --- |
| `,ad` | Toggle file explorer / checkout changes |
| `,aa` | Tag the current line or visual selection with a comment |
| `,as` | Choose a recipient, then send queued tags |
| `,at` | Choose the default agent without sending |

`:HerdrCode` does the same files/changes toggle. Both views keep their buffers,
cursors and queued tags. File search (`,tt`, `,tg`), comment preview (`,ap`),
and direct questions (`,ac`, `,ar`) still use the existing Neovim controls.
The older `,af` (files), `,ab` (return), `,ae` (full tab) and `,aS` (send) shortcuts
remain as aliases; they are not needed for the basic workflow. These local Code
controls do not change mappings in ordinary Neovim or legacy review panes.

From an agent, `Ctrl+a`, then `r`, opens changes in the full Code tab rather
than beside the agent. Reviews start inline with the changed-file list hidden.
`,b` shows or hides that list; `t` switches between inline and side-by-side.
`]f` / `[f` navigate files even with the list hidden; `]c` / `[c` navigate hunks.
`gc` folds unchanged code. Closing CodeDiff with `q` returns to files, not to
the agent. `Ctrl+a e` or `,ab` returns to the source pane. Files changed on disk
reload through the existing Neovim watcher; modified buffers are not overwritten.

Every tag delivery opens a recipient picker first, including `,as`, the older
`,aS`, and `:HerdrSend`. Only current agent panes in this Herdr session are listed,
not saved/stopped conversations. Type to filter by number, pane ID, agent kind,
status, directory, summary or reported session ID. The previous/default recipient
is first, followed by other agents in this workspace. Enter confirms and sends;
Escape cancels and keeps the queued tags. Empty or failed agent lists also keep
the tags and allow another attempt.

The default initially comes from the agent that created the editor. The window
header shows its captured sidebar number, stable pane ID and task summary.
`,at` changes that default without sending. Direct questions use the default;
tags always require confirmation, even when a default exists. Each worktree keeps
its own default. Selecting an agent rechecks the displayed pane, terminal and
reported conversation identity before saving the choice; delivery checks again,
including Yuke's session token. Replaced agents refuse delivery and keep tags or
question drafts. Agents without reported session identity can only be checked by
pane, terminal and kind. Opening, dismissing or switching the editor never
submits a prompt.

Changes compare a jj checkout with `@-` or a Git checkout with `HEAD`. They include
manual edits and other agents' work in that checkout. Opening a jj diff snapshots
normally; it does not create a new change or bookmark. Code editing also works in
non-colocated jj workspaces, but their diff view reports that CodeDiff requires a
Git-backed checkout. Agent-only attribution and historical checkpoints are not
implemented.

The Code tab owns the headless editor. Hiding it keeps the process alive; closing
its Herdr tab ends it. A lifetime pipe also ends Neovim if its owner disappears.
Before shutdown it attempts to save unsaved buffer text in a private recovery
file, not in the original files. Reopening the same checkout/workspace restores
those buffers as modified and labels them as recovered. This is best-effort crash
recovery, not durable preservation of every editor setting or queued annotation
across tab closure. If the editor is stuck during shutdown, it exits after three
seconds; see its `.log` file for recovery failures. Runtime records, logs and
recovery files live in Herdr's state directory under `plugins/david.code/`.

Sources and the Lua adapter live in `local-plugins/code`; they do not modify the
Neovim submodule or install another copy of `herdr-nvim`. The adapter uses the
existing personal Neovim config and its pinned `herdr-nvim`, CodeDiff and jj.nvim.
On a new machine after Stow has linked the package:

```sh
herdr plugin link "$HOME/.config/herdr/local-plugins/code" --enabled
herdr config check
herdr server reload-config
```

An already-attached client may need `Ctrl+a Shift+r` to reload its local keys.
Existing Code editors keep their running host and loaded Lua; server/client config
reload does not update their host directory or Vim behavior. To load plugin
updates, save your work and finish any queued tags, then close and reopen that
Code tab. The plugin does not restart active editors automatically.
Scrollback editing uses `Ctrl+a`, then `Ctrl+e`. Checkout review uses `Ctrl+a r`.
The legacy split remains available through `david.review.toggle`.

Verification uses only private sessions and detached terminals:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 "$HOME/.config/herdr/local-plugins/code/tests/test_code.py"
PYTHONDONTWRITEBYTECODE=1 python3 "$HOME/.config/herdr/local-plugins/code/tests/check-code.py"
```

The live check requires Neovim, Herdr, tmux, jj and the linked plugin. It uses the
installed Herdr by default; set `HERDR_CODE_TEST_BIN` to an absolute binary path
to test another build. It checks initial pinning, event-driven re-pinning,
multi-worktree ordering, checkout directories for the host and Neovim, automatic
checkout names and ordinary Code-named tabs. It also exercises
file-tree selection, files/changes toggling, tagging and sending through actual
shortcuts, ten tab/overlay cycles, insert-mode edits, cursor preservation,
resizing, external file reload, and worktree isolation. Delivery uses a capture
executable; a real companion check verifies that blocked agents receive no
terminal input. It also covers replaced agent sessions, simulated Yuke session
rejection, explicit retargeting, immediate close/reopen recovery and owner/session
shutdown. No model or live-agent prompt is used. It saves
`/tmp/herdr-code-integration-result.json`.

## Neovim checkout review (legacy split)

The local `david.review` plugin opens a persistent Neovim split beside the
invoking pane, using that pane's actual checkout. Wide panes split right;
narrow ones split down. CodeDiff uses the same inline default and hidden
changed-file list as Code; `t` changes the layout inside the diff.

The split is no longer bound to `Ctrl+a r`. The action
`herdr plugin action invoke david.review.toggle` opens it from the calling pane
or returns from the review pane. `,ab` or `:HerdrReviewReturn` also returns to
the source pane. Closing the CodeDiff tab with `q` returns automatically. The
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

## Code panel identity

Pinned editor tabs use the label `Code`. The plugin reports `pane_kind=editor` only for panes whose saved terminal and workspace ownership still match. The workspace metadata plugin ignores editor panels when it selects a checkout. The native workspace-identity patch also derives automatic project labels from regular tabs before editor tabs. It preserves custom workspace names and does not remove ordinary tabs. The native patch needs a verified newer Herdr build; no native installation occurs through editing these dotfiles.
