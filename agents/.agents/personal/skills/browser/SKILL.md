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

Across backends:

- Browser UI operations are pre-authorized inside the configured backend.
- Each activity owns a distinct visible session or tab group. Never use David's
  tabs, another activity's session, or a tab while a person controls it.
- If David needs to log in or repair a page, pause browser actions, let him use
  the owned tab, and continue only after he says it is ready. Refresh the
  snapshot before resuming.
- Give parallel stateful flows separate short, stable activity names.
- Keep an activity attached after responding so David can inspect it and later
  follow-ups can reuse its state. Detach only when David explicitly says the
  activity is done or asks to detach it.
- Before an irreversible external action, confirm only when the user's request
  did not already authorize that exact action and destination.

## Configured backends

Resolve the backend before operating the browser, in this order:

1. Use an inherited `DAVAFONS_BROWSER_BACKEND` when set.
2. Otherwise, check `~/.config/playwright-cli/env` for a configured backend.
   Read only the backend value in a subshell; never print the file or its token:

   ```bash
   bash -c 'if [[ -f "$HOME/.config/playwright-cli/env" ]]; then source "$HOME/.config/playwright-cli/env" >/dev/null 2>&1; printf "%s\n" "${DAVAFONS_BROWSER_BACKEND:-}"; fi'
   ```

3. If neither supplies a backend, a Codex session identified by
   `CODEX_SESSION_ID` uses `brave-extension`.

Pass the resolved `DAVAFONS_BROWSER_BACKEND` to each browser command when it
was not inherited. For Yuke and other non-Codex controllers, also set a unique
`PLAYWRIGHT_CLI_SESSION` as described in the Brave reference. Missing inherited
variables alone do not establish that the browser is unconfigured.

- For `brave-extension`, read
  [references/brave-extension.md](references/brave-extension.md).
- For `camofox`, read [references/camofox.md](references/camofox.md).
- If neither an explicit supported value nor a Codex session identifies the
  backend, stop and report that no supported backend is configured.

Future backends such as Firefox must be configured explicitly. Never infer a
backend from an installed application.
