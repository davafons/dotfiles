# Project work

`/work` shows two tabs, **Board** for shared project tasks and **GitHub** for read-only issue and PR review. Linked jj checkouts and Git worktrees share the same task board. Each task records its creator separately from its current owner.

`1` opens the board. `2` opens GitHub. Tab and Shift+Tab cycle between them. The project context and Handoffs tabs, their shortcuts, and `/checkpoint` are removed. Agents no longer receive context or checkpoint actions or instructions to maintain those records. Historical database records remain untouched. The private storage helper accepts the old request format so already-running profiles keep working until their next idle reload. Updated profiles use a task-only request format and do not read or maintain those records.

## Board navigation

The board groups tasks by `now`, `later`, `blocked`, `review`, and `done`. Click **Show done** or **Hide done** to change completed-task visibility. There is no keyboard shortcut for this control. Each column shows its visible item range, total count, above and below indicators, and a proportional scrollbar when needed. The range describes visible cards, not all five records loaded in the current page. The final range says `end`.

Empty columns use four-cell vertical rails by default. Each rail shows the stage name vertically and its task count. Populated columns share the remaining width.

Scrolling through a collapsed column temporarily previews its tasks. Leaving that column collapses the preview again, including when focus moves with the mouse wheel. Browsing never changes the saved expansion preference. `z`, a header click, or Enter on a collapsed column explicitly expands it. Explicitly expanded columns stay open while you visit other columns. While a temporary preview is open, the footer labels `z` as `keep open`.

`z` or a header click collapses an explicitly expanded column. `Z` resets all columns to automatic sizing. These choices last while the work dialog is open. Expanding a column does not change its task status or reveal hidden completed tasks.

Arrow keys and `h`, `j`, `k`, and `l` move between columns and cards. Moving beyond a loaded page continues into the next page. `n` and `p` change the selected column's page explicitly. The mouse wheel moves the column under the pointer. A wheel event over task details scrolls those details instead.

Enter opens the selected task inspector. Task details occupy the left column. Actions occupy a separate right column. Arrow keys select an action, and Enter runs it. Left moves keyboard focus to the details. Right returns focus to the actions. PageUp and PageDown scroll the details without changing the task. Escape returns to the board.

Notes, task messages, and GitHub bodies use Yuke's Markdown renderer. It preserves styled segments, headings, emphasis, code, lists, and block spacing. Task IDs and checkout paths remain plain text.

## Ownership and coordination

A task has at most one owner session and owner checkout. `claim` requires a fresh task version, claims an unowned task, and moves it to `now`. Saving a task as `now` also claims it when it has no owner. Simultaneous claims have one winner. A different session cannot replace the owner's notes or change its status.

`release` requires a fresh version and the owning session. The inspector also lets an operator clear another session's abandoned claim after confirmation. That action does not stop the other agent. Setting a task to `done` clears its claim.

An open board and model `list` or `get` reads reconcile closed owners automatically. The check resolves a child to its native root tree, then opens that tree's existing ownership lock read-only. It clears assignments only after it acquires the exclusive lock and verifies the lock-file identity. The check holds that lock through the version-checked task update. A visible native chat or a live reported pane retains its assignment even before a model turn acquires native ownership. Cleanup requires repeated closed observations spanning three seconds, so transient reloads do not immediately release work. Open or unknown observations reset that grace period. A system task message records the previous owner and the reason. Notes and task status stay unchanged.

Idle and blocked owners keep their assignments. A live headless owner or child tree also stays protected. Missing lock support, inaccessible files, unreadable chat metadata, an unavailable pane inventory, or an unknown tree retain the assignment. An empty chat that has never acquired native ownership remains unknown. A chat hidden from the UI can still belong to an active engine; absence from the pane list alone never releases it.

Each parallel worker, including a child agent, claims a separate task. One chat can own several scoped tasks, so task counts can exceed open agent counts. The board reports distinct owner chats and assigned tasks, and cards show when the same chat owns several tasks.

Owner labels use Herdr's actual `shortcut_number`, such as `Agent 2`, plus the chat title or reported summary. They are not invented numbers. Child labels include the parent agent number and the native child name/ID. Task details show the model, assigned-task count, parent chat when applicable, full owner session ID, and checkout. Without a reported agent number, the label uses the chat identity instead.

Claims coordinate task records. They are not file locks or a source-code sandbox. Agents still need distinct scopes and checkouts where appropriate.

The `notes` action updates only task notes with a fresh version. It preserves status, ownership, creator, checkout, and links. It refuses edits by another task owner. The inspector uses this operation, so editing an unclaimed Now task's notes does not claim it.

A task message appends Markdown text with the author's session, checkout, and time. It does not replace task notes or require the task's current version. `get` and the inspector show the latest 20 messages. The open board refreshes records every three seconds. Messages do not notify another agent or start a model turn. An agent reads them with `get`.

Clicking an owned card opens its owner session, including when that session is idle or waiting. A session reported in another Herdr pane uses that pane's existing navigation. Other sessions open in the current Yuke pane. An unsent draft prevents replacing the current session. Keyboard selection and Enter remain available for inspecting an active task without navigating away.

Legacy tasks start unclaimed. The plugin does not infer ownership from `now` or the creator. Existing Yuke processes need `/reload` when idle to load the updated tools and instructions. Their agents must then claim the task they are actually working on. Refreshing the board alone does not establish ownership.

For unclaimed tasks, `s` opens the recorded source session. The card and inspector label the action `Open linked chat`. When the task has an owner, the inspector says `Open owner chat`. Viewing a linked chat never claims its task.

## Activity observations

Cards distinguish task ownership from observed session activity. An owned task follows its explicit owner. Unclaimed cards say `Unclaimed` and offer `s: Open linked chat` and do not animate from a linked conversation's activity. The inspector can show linked-session activity, explicitly labeled as not task work. A busy conversation can be linked to many tasks that it is not currently working on.

An open local session supplies native activity. Otherwise a Herdr report supplies the reported state. Without either, a native session read can observe a child without a TUI pane or a session known to this engine. A parent's pane supplies a child's agent identity, not its activity. Missing sessions and failed reads show `unavailable`. A state observed in this engine does not establish what another engine is doing. Native tree-lock ownership is checked separately before automatic release.

Activity reads run once per second while the dialog is open. A moving marker means the observed session is running. The marker does not change the task's saved status. Drawing paints cached spans and performs no storage or socket requests. Closing the dialog stops polling and rejects late results.

## GitHub review

The GitHub tab reads issues and PRs through the authenticated `gh` CLI. `v` switches between issues and PRs. `o` cycles through open, closed, and all records. `n` and `p` change pages. The details show the body, reported review status, CI rollups, and up to 20 checks for a PR.

Enter shows linked internal tasks. `a` adds an internal step linked to the selected GitHub item. These actions do not import other items or synchronize task status with GitHub. The plugin never posts reviews, comments, merges, or other GitHub writes.

## Checks

```sh
python3 -B yuke/tests/check-project-work-store.py
node yuke/tests/check-project-work-view.mjs
python3 -B yuke/tests/check-work-activity.py --binary /absolute/path/to/verified/yuke
```

The store tests use disposable databases and include simultaneous claim attempts, owner-only edits, linked checkouts, message attribution, version conflicts, legacy migration, live native locks, closed-owner release, idempotence, stale-owner observations, and unknown/symlink refusal. The view tests check viewport ranges, page boundaries, owner routing, late results, and cached drawing.

The native driver verifies the two tabs, keyboard cycling, retired commands, and issue and PR details through a local `gh` fixture. It uses a private socket and detached terminal with the source profile. It drives Markdown details, the action column, scrolling, owner navigation, task messages, and claim refusal. It creates saved fixture chats without contacting a provider. A second owned terminal records a fixture command through the public API to acquire real native ownership, stays assigned while idle, and is then closed to verify automatic unassignment. Both owned terminal processes must exit during cleanup. Its socket navigation is a fixture, not proof that the user's live Herdr pane switched. It focuses no user window, uses no real credentials, and leaves the clipboard untouched.
