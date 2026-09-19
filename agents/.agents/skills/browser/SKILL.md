---
name: browser
description: Research current public information or navigate and debug websites through the configured tools and visible browser backend.
---

# Browser

Use only the backend configured for the current runtime. A missing backend is a
connection problem, not permission to launch a hidden browser or substitute a
different controller.

For public research, source comparison, shopping research, or current facts,
read [references/research.md](references/research.md). Use the browser only
when search and extraction are insufficient or the task requires interaction.

The shared contract is:

- Browser work remains visible and available for David to inspect or take over.
- Each agent and activity owns a distinct session and tab group. Never use
  David's tabs, another activity's session, or the same tab concurrently with
  a person.
- If David needs to log in or repair a page, pause browser actions, let him use
  the owned tab, and continue only after he says it is ready. Refresh the
  snapshot before resuming.
- Keep normal navigation and diagnostics in the existing owned tab. New tabs,
  popups, dialogs, and tab selection can disrupt foreground work, so use them
  only when the task requires them.
- When one agent needs genuinely parallel, stateful browser work, give each
  flow a short stable activity name rather than sharing one group.
- Keep an activity attached after responding so David can inspect it and later
  follow-ups can reuse its state. Detach only when David explicitly says the
  activity is done or asks to detach it.
- Stop immediately before purchases or other irreversible actions and request
  confirmation.

## Configured backends

Resolve the backend before operating the browser. An explicit
`DAVAFONS_BROWSER_BACKEND` wins; when it is unset, a Codex session identified
by `CODEX_SESSION_ID` uses `brave-extension`:

- For `brave-extension`, read
  [references/brave-extension.md](references/brave-extension.md).
- For `camofox`, read [references/camofox.md](references/camofox.md).
- If neither an explicit supported value nor a Codex session identifies the
  backend, stop and report that no supported backend is configured.

Future backends such as Firefox must be configured explicitly. Never infer a
backend from an installed application.
