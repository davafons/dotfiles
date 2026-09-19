# Herdr on the Mac

The `mb` profile installs this package with GNU Stow.
`~/.config/herdr/config.toml` points to `.config/herdr/config.toml` in this package.
The `tower` profile uses the separate `herdr-tower` package.

Press `Ctrl+a`, release it, then press the action key.

| Action key | Action |
| --- | --- |
| `Ctrl+p` / `Ctrl+n` | Previous / next agent across workspaces |
| `Ctrl+1` through `Ctrl+9` | Jump to agent 1 through 9 |
| `w` | Open workspace navigation |
| `Shift+1` through `Shift+9` | Jump to workspace 1 through 9 |
| `Shift+p` / `Shift+n` | Previous / next workspace |
| `Shift+c` | Create a workspace |
| `t` | Open the fuzzy navigator |
| `g` | Create a jj workspace or Git worktree from `main` |
| `Shift+g` | Pick an existing jj workspace or Git worktree |
| `Shift+u` | Refresh checkout sidebar status |
| `h` / `j` / `k` / `l` | Focus the pane to the left / down / up / right |
| `p` / `n` | Previous / next tab |
| `1` through `9` | Jump to tab 1 through 9 |
| `Shift+Tab` / `Tab` | Previous / next pane |
| `,` | Rename the current pane |
| `[` | Enter copy mode |
| `?` | Show the active keybindings |

Direct `Ctrl+p` and `Ctrl+n` pass through to the application.
New tabs open immediately with generated names. Tabs containing detected agents
show the same state symbol as the agent sidebar plus their global shortcut
number, for example `◐[3] 2`; terminal-only tabs keep their ordinary name.

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
Workspaces and agent entries show their actual checkout rather than inferring it
from a manually assigned Herdr label. A workspace follows its active tab's
selected pane; each agent follows its own pane. Workspace rows show:

- jj workspace name, short change ID, description, saved changed-file count,
  bookmarks, and `CONFLICT` when present.
- Git checkout directory, branch (or detached HEAD), current changed-file count,
  and conflicts, including linked Git worktrees.

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

After a config edit, run `herdr config check`, then `herdr server reload-config`.
If an attached client retains its old keys, press `Ctrl+a`, then `Shift+r` to
reload its local config.

See the [keyboard guide](https://herdr.dev/docs/keyboard/) for the built-in keys.
