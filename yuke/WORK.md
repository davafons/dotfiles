# Project work and live session activity

`/work` shows persistent tasks, project context, saved checkpoints, and read-only GitHub work. Its Board groups tasks by `now`, `later`, `blocked`, `review`, and `done`. Those stages are task records, not engine states.

Each task card shows the latest known linked session observation. The view uses a task's loaded checkpoint first, then a recent matching checkpoint, then its recorded source session. An open local session supplies its native activity. Otherwise the view uses the session state reported through Herdr's `pane.list` API. The label identifies `here` or `Herdr`. A missing session, missing report, or failed read shows unavailable. It never implies idle or completion.

A moving marker means that the observed session is working. An idle, blocked, or done report from Herdr does not change the task's saved stage. Closed old source chats remain unavailable after the fresh-database cutover. Prepare a task brief and save a new checkpoint to link new work.

Activity reads run once per second while the dialog is open. Marker ticks select prebuilt strings. Drawing performs no storage read, socket request, clipping, wrapping, or cache rebuild. Closing the dialog stops its timers, cancels owned reads, and rejects late results.

## Task lifecycle

The agent receives instructions to read `/work`, update tasks with a fresh version, save checkpoints after meaningful progress, and record verification honestly. These instructions guide the agent; they do not enforce automatic stage transitions. The store checks versions and ownership. The UI does not mark a task done because its session stops running.

Use `now` for current work, `later` for deferred work, `blocked` for a required missing decision or capability, `review` for work that needs a review or installation decision, and `done` for a completed or explicitly closed record. Explain obsolete or canceled work in its notes. A session end alone is not completion evidence.

A checkpoint records progress, decisions, the next action, and checks that passed, failed, or did not run. A later run start can mark it stale. It does not complete its linked task. GitHub reads do not import tasks or write issues, PRs, or statuses.

## Checks

```sh
node yuke/tests/check-project-work-view.mjs
python3 -B yuke/tests/check-work-activity.py --binary /absolute/path/to/verified/yuke
```

The native check uses a private Herdr socket and a detached terminal with the full source profile. It proves that working, idle, and blocked reports update the view, that idle preserves the task stage, and that closing stops polling. It also checks that the startup dashboard includes Search and Work after all plugins register. It sends no model request, focuses no user pane, and uses no real credentials.
