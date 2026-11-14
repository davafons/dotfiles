# Project work

The `project-work` plugin provides `/work`, the model tools `project_work` and `github_work`, and a row above the composer for the current session's task. Its entry is `"./plugins/project-work"` in `config.json`.

Tasks are stored in `~/.local/share/yuke-rust/plugins/project-work/work.sqlite3`. Linked jj workspaces and Git worktrees share one task list. Nested repositories keep separate lists. A folder outside version control has its own list.

## The work dialog

`/work` opens a list on the left and details on the right. Tab cycles between tasks, GitHub issues, and GitHub PRs. The title shows the tab, the total count, and the workspace.

The task list shows ten tasks per page, newest update first. Each row shows the status, title, and owner session or `unassigned`. Completed tasks are hidden by default. Type to filter the loaded rows. Up and Down select a row.

The details show the title, status, task ID, version, owner session, linked GitHub URL, notes, and the latest 20 messages. They use Yuke's Markdown renderer.

| Key | Action |
|---|---|
| Tab | Cycle tasks, issues, and PRs |
| Enter | Focus the details |
| Ctrl+F | Switch focus between list and details |
| Ctrl+R | Refresh |
| Ctrl+N | Next page |
| Ctrl+P | First page |
| Ctrl+D | Show or hide completed tasks |
| Alt+N | New task |
| Alt+E | Edit the selected task |
| Alt+M | Post a message on the selected task |
| Ctrl+G | Claim or release the selected task |
| Alt+U | Unassign the owner after confirmation |
| Ctrl+O | Open the owner session |
| Esc | Close |

The dialog does not refresh on a timer. It reloads after its own changes and on Ctrl+R.

### Edit a task

Alt+N and Alt+E open a form with a title, notes, and an optional github.com issue or PR URL. Tab moves between the fields. Ctrl+T chooses the status. Ctrl+S saves. A new task starts as `later`.

Alt+M opens a message editor. Ctrl+S posts the message. It does not notify another session or start a model turn.

Ctrl+G, Alt+M, and claiming by saving as `now` need a saved session in the active pane.

### Open the owner

Ctrl+O opens the owner session in the current pane. If that fails and Yuke runs in Herdr, it focuses the Herdr pane that reports that session.

### Composer row

When the current session owns a task, a row above the composer shows `work  <title> · <status> · /work`. It updates when the chat changes and after each `project_work` call.

## Statuses and ownership

Tasks have one of five statuses: `now`, `later`, `blocked`, `review`, and `done`.

A task has at most one owner session. A session can own only one task across all projects. Complete or release the current task before claiming another. Simultaneous claims have one winner. Child agents use their own sessions.

`claim` requires a fresh version, assigns an unowned task to the session, and moves it to `now`. A completed task must be reopened before a claim. Saving a task as `now` also claims it when it has no owner. Setting a task to `done` clears its owner.

`release` requires a fresh version and the owning session. It keeps the status. Alt+U lets the operator clear another session's abandoned claim. That does not stop the other agent.

Another session cannot change an owned task's title, status, or notes. It can post messages.

The board and the `list` and `get` reads release a claim automatically only when its owner is closed. They walk each owner session to its native tree root, and treat a session that this process has open as open. The store then reads the root's session lock and the Herdr pane inventory. A claim is released only when the lock is free, Herdr is reachable and shows no live Yuke pane for the session, and both still agree after a grace period. Idle, blocked, unknown, and deleted sessions keep their claims. A released task gets a system message, and its status and notes stay. Outside Herdr nothing is released automatically.

Otherwise a claim stays until its owner releases it, the task is done, or the operator unassigns it.

Claims coordinate task records. They are not file locks or a source-code sandbox. Agents still need distinct scopes and checkouts where appropriate.

## The `project_work` tool

| Action | Behavior |
|---|---|
| `list` | Ten tasks from `offset`. `include_done` adds completed tasks. |
| `get` | One task and its latest 20 messages. |
| `task` | Create a task without `id`, or update title, status, notes, and `github_url` with `id` and `version`. |
| `notes` | Replace only the notes. Keeps status, owner, and links. Does not claim. |
| `claim` | Assign the task to this session. |
| `release` | Clear this session's assignment. |
| `message` | Append a Markdown message. Needs no version. |
| `progress` | Append a message and optionally change status in one transaction. |

Updates, `notes`, `claim`, `release`, and `progress` require the version from the latest read or mutation receipt. A stale version fails without a change. Read the task again after a conflict.

An empty `github_url` clears the link. An omitted one keeps it. Internal status never updates GitHub.

### Record progress

After claiming a task, call `progress` with `id`, `version`, and a short Markdown `body`. Include `status` when the status changes. The task's title and notes stay unchanged. `done` releases ownership.

Only the owner can record progress. Replaying the same tool call returns its original receipt without repeating the change. A replay with different arguments fails. The receipt describes that earlier change, not necessarily the current task.

Use `task` or `notes` for scope changes.

### Agent instructions

The plugin adds a prompt section. It tells agents to read tasks when starting or resuming work, claim a task before working on it, prefer `progress` for routine updates, keep notes current, and coordinate through messages when another session owns a task. It says that reading records does not authorize delegation, external messages, pushing, merging, or deployment.

## GitHub

The Issues and PRs tabs list items through the authenticated `gh` CLI. They list open items, 20 per request, newest update first. Each row shows the number, title, state, and CI rollup. Ctrl+N loads the next page. Ctrl+P returns to the first page.

With a GitHub item selected, Alt+N opens a new task with that item's title and URL.

`github_work` gives agents the same reads. `list` reads the checkout's repository and accepts `kind` (`issues` or `pulls`), `state` (`open`, `closed`, or `all`), and `cursor`. `get` takes `number` with `kind`, or a github.com issue or PR `url` such as a task's `github_url`. A URL sets the repository and kind.

The details view of a GitHub row reads the item by its URL.

The plugin never posts reviews, comments, merges, or other GitHub writes. It supports github.com repositories only.

## Checks

```sh
python3 ~/dotfiles/yuke-rust/scripts/verify.py --source ~/workspace/yuke --binary ~/.local/lib/yuke-rust/bin/yuke
```

`tests/test_project_work_store.py` uses disposable databases. It covers progress receipts and replays, stale and foreign changes, linked jj and Git checkouts, nested repositories, version conflicts, atomic claims, one task per session, notes-only edits, messages that keep notes, GitHub links, paging, legacy duplicate assignments, and unknown lock evidence.

`tests/tools.test.ts` checks that a claimed task keeps its scope through progress and completion.

`tests/terminal.py` opens `/work` in a detached terminal, creates a task with Alt+N and Ctrl+S, and sees it in the list. It makes no model request.

No test covers the GitHub tabs.
