# Project work

Open `/work` for a full-screen project view, like `/usage`. The board shows project
tasks in colored status columns. The other tabs show the project goal, decisions,
and recent work checkpoints. A fourth tab reads GitHub issues and PRs.
The plugin stores these records outside the repository. It does not change project files.

## Commands

| Command | Action |
| --- | --- |
| `/work` | Open the project work view. |
| `/todo <title>` | Save a task with status `later`. |
| `/todo` | Ask for a task title. |
| `/checkpoint` | Ask where work stopped, what comes next, and what verification ran. |

The command palette also lists these commands. Use the palette to open work while
an unsent draft remains in the composer. Opening or closing the view preserves that draft.

## Full-screen view

The board uses five columns: **Now** (blue), **Later** (cyan), **Blocked** (yellow),
**Review** (violet), and **Done** (green). The selected card has a colored background
and a `>` marker. Text labels identify each status without color. Colors follow the
profile theme in dark and light backgrounds, with truecolor and 256-color output.

The kanban board uses the full terminal width. The selected task's explanation
stays below the board at every width. The Checkpoints tab also shows its explanation
below the cards. PageUp and PageDown scroll the explanation. Below 95 columns, the
board shows one column at a time. Left and right still navigate all five columns.
The view needs at least 45 columns and 19 rows.

The board reads five tasks per column page. Each column shows its count and page
range. Completed cards stay hidden until you press `d`. Filtering searches task
titles and notes across the project, not just the current page. Refresh reads the
latest records; the view does not poll.

| Key | Action |
| --- | --- |
| `1`, `2`, `3`, `4` | Open Board, Context, Checkpoints, or GitHub. |
| `Tab`, `Shift+Tab` | Switch tabs. |
| `h` / `l`, Left / Right | Switch board columns. |
| `j` / `k`, Down / Up | Select a task or checkpoint. Scroll the Context tab. |
| `Enter` | Open task actions, edit project context, or resume a selected checkpoint. |
| `a` | Add a task. |
| `m` | Set the selected task's status. |
| `c` | Save a checkpoint. In Board, link it to the selected task. |
| `g` | Edit the project goal and decisions. |
| `b` | Prepare a brief for the selected task. |
| `s` | Resume the selected task or checkpoint's session. |
| `/` | Filter tasks. Submit a blank query to clear it. |
| `d` | Show or hide completed cards. |
| `n` / `p` | Read the next or previous page in the selected column. |
| PageUp / PageDown | Scroll details. |
| `r` | Refresh. |
| `Esc`, `q` | Return to the conversation. |

Click tabs, column headings, cards, and visible controls to select them. Double-click
a task for its actions. Double-click a checkpoint to open its session. The mouse
wheel moves through cards or scrolls details, based on its position.

Select a task to read its notes and linked checkpoint. Press `Enter` to edit notes,
prepare a brief, resume the linked session, save a checkpoint, or change status.

**Prepare a brief** fills an empty composer. It does not send the brief or start an
agent. It refuses to replace an existing draft. A checkpoint from another checkout
requires you to resume its linked session first.

**Open linked session** opens the newest task checkpoint's session, or the session
that originally captured the task when no linked checkpoint exists. It refuses to
replace an unsent draft. When the session has a reported owner in another Herdr
pane, it uses the existing Herdr navigation integration. Yuke's session ownership
checks still apply when no owner is reported.

A task captured before a conversation starts has no session link. Save a checkpoint
from a saved conversation to associate that task with a session.

## Inner and outer loops

Internal tasks are the inner loop. Use them for investigation, implementation,
verification, blockers, and deferred steps. They belong to the project and survive
sessions. They are not private to one agent. A source session link identifies the
conversation that captured a task.

GitHub is the outer loop. The GitHub tab reads issues, PRs, review decisions, and CI
state from the repository that `gh` selects in the calling workspace. Internal tasks
can have a `github_url` link. One issue or PR can have many internal steps.

The two loops keep separate states. Marking an internal task done does not close an
issue, approve a review, or merge a PR. A merged PR does not mark internal tasks done.
The plugin never imports every GitHub issue into the internal board.

## GitHub view

Press `4` in `/work` to open GitHub. Install the GitHub CLI and authenticate with
`gh auth login` first. The view uses the CLI's credentials; it does not ask for or
store a token. This version supports `github.com` repositories. It does not support
GitHub Enterprise hosts.

| Key in GitHub | Action |
| --- | --- |
| `v`, Left, Right | Switch issues and PRs. |
| `o` | Cycle open, closed, and all. Closed PRs include merged PRs. |
| `j` / `k`, Down / Up | Select an item. |
| `n` / `p` | Read the next or previous cursor page. |
| `a` | Capture a linked internal step with status `later`. |
| `Enter` | Open linked internal task actions, or capture the first step. |
| PageUp / PageDown | Scroll the explanation below the list. |
| `r` | Read a fresh GitHub snapshot. |

Each page has up to 20 items. PR cards show GitHub's review decision and CI rollup.
A null review or CI value means GitHub did not report it. It does not mean approval
or passing checks. The detail area shows up to 20 CI checks and up to 50 linked task
summaries. The issue or PR body preview has a 300-row limit. The `github_work` tool
returns the body rather than the UI preview.

The plugin reads GitHub on demand. It does not poll or install webhooks. Opening the
internal board does not fetch GitHub. Authentication, permissions, and network errors
appear in the GitHub view without removing internal records. Closing the work view
cancels and waits for its active GitHub reads.

Capturing an internal step only changes the local task store. The plugin sends no
GitHub mutations. It does not post comments, edit issues, close issues, approve
reviews, push branches, or merge PRs. URLs remain visible in the UI; the plugin does
not activate a browser or copy them to the clipboard.

## Agent records

The `project_work` tool works in the TUI, headless mode, and RPC mode.
Every operation uses the calling session's project. The model cannot choose another
root or session through tool arguments.

| Action | Required fields |
| --- | --- |
| `list` | None beyond `action`. Optional `offset` pages through tasks. Optional `include_done` includes completed tasks. |
| `get` | `id` of a task. Returns the full task and its newest linked checkpoint. |
| `task` | `title`, `status`, `notes`. Add `id` and the current `version` to update an existing task. Optional `github_url` links a GitHub issue or PR. Empty clears it; omission preserves it on an update. |
| `checkpoint` | `summary`, `next_step`, `verification`. Optional `task_id` associates it with a task. |
| `context` | `goal`, `notes`, and the current context `version` from `list`. A new context has version `0`. |

The separate `github_work` tool reads the outer loop. It also works in TUI,
headless, and RPC modes. The model cannot select another root or repository through
tool arguments. No action writes to GitHub.

| Action | Fields |
| --- | --- |
| `list` | Optional `kind` (`issues` or `pulls`), `state` (`open`, `closed`, `all`), and `cursor`. Defaults to open issues. Returns up to 20 items, a total, and the next cursor. |
| `get` | `number` and optional `kind`. Returns the body, reported review/CI, check details for PRs, and linked internal task summaries. |

The profile instructs agents to read GitHub when their work refers to an issue or
PR. It instructs them to keep internal steps and verification in `project_work`.
Preparing a linked task brief adds its GitHub URL and a reminder to read the outer
state before continuing. This is model guidance, not an enforced background planner.
The board does not automatically inject all records into every model prompt. The
agent reads them through the tools.

For example, an agent can save a deferred task with these arguments:

```json
{
  "action": "task",
  "title": "Investigate slow history loading",
  "status": "later",
  "notes": "Measure loading before changing the cache. No benchmark has run."
}
```

The profile tells agents to read work when they start or resume substantial work.
It tells them to save checkpoints after meaningful progress and before they stop or
wait for a decision. This is agent guidance, not an enforced automatic summary.
The plugin does not invoke another model to reconstruct an incomplete record.

A checkpoint states the progress, the next action, and the verification. It retains
the source session and checkout. Each session has one current checkpoint per project.
Saving another checkpoint replaces that session's previous checkpoint.
The view shows the five most recently saved session checkpoints.

A run start recorded after a checkpoint makes that checkpoint `STALE`. The warning
survives a restart. It means that a later run may have changed the work. It does not
mean that the task failed. A missing warning does not prove that a run finished, or
that no later actions occurred within the same run. Read the source conversation
and inspect the checkout before continuing. Child run starts do not invalidate a
parent session's checkpoint.

Saving a checkpoint never marks a task done. A run ending never marks a task done.
Record the checks that did not run instead of inferring success.

## Storage and concurrent sessions

Records live at:

```text
$XDG_STATE_HOME/$YUKE_APPNAME/work/work.sqlite3
```

The default path is `~/.local/state/yuke/work/work.sqlite3`.
The directory has mode `0700`. A newly created database has mode `0600`.
The helper refuses a database symlink.

Linked jj workspaces share the jj repository identity. Linked Git worktrees share
the common Git directory identity. A colocated checkout uses jj identity. A nested
repository keeps its own records. A directory without version control uses its
resolved path as its project identity.

SQLite serializes writers across processes. Task and context updates require a
version from a recent read. An outdated edit fails and asks you to refresh. Replaying
a task-creation tool call returns the same task rather than creating a duplicate.
A status or note edit retains the task's original session link.

The helper needs Python 3 with its standard `sqlite3` module. No Python package is
required. Storage errors appear as tool failures or UI notices. The view reads
records when you open or refresh it. It does not poll or read files during draw.

## Verification

```sh
python3 ~/.config/yuke/tests/check-project-work-store.py
node ~/dotfiles/yuke/.config/yuke/tests/check-project-work.mjs
node ~/dotfiles/yuke/.config/yuke/tests/check-project-work-view.mjs
python3 ~/dotfiles/yuke/.config/yuke/tests/check-project-work-github.py
python3 ~/.config/yuke/tests/check-project-work-tui.py
tsc -p ~/.config/yuke/jsconfig.json
yuke check
```

The terminal test uses a detached, private tmux server and temporary XDG directories.
It uses a local HTTP model fixture and an isolated `gh` substitute, not a remote
model or live GitHub credentials. It never attaches to a terminal,
activates an application, uses the clipboard, or modifies regular sessions.
It saves labeled screen captures in a temporary text artifact. It checks the full
view, status colors, card contrast, tabs, keyboard and mouse navigation, filtering,
column pages, narrow layouts, draft preservation, GitHub tool reads, task links,
PR review/CI, and cancellation of a pending GitHub read. Run it with `--colors 256`
and `--background light` to check the other palette modes. The view test verifies
that repaint uses cached text and does not read storage, wrap, or clip again.

Restart Yuke after installing the plugin. The custom profile reloader also supports
`/reload`, but the current run keeps its original tool loadout.

## Not included

This version does not write to GitHub, synchronize internal and external statuses,
or manage GitHub Projects boards. It does not add a Herdr project overview, create
checkouts, delegate work, or post external updates. Those integrations can read the
same work records in a later version.
