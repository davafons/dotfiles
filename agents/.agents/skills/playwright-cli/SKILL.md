---
name: playwright-cli
description: Drive the user's visible, logged-in Brave profile through an isolated Playwright CLI extension connection, independently opening requested pages while allowing other agents to control separate tab groups concurrently.
---

# Playwright CLI

Use this skill for browser work that needs the user's existing visible Brave
profile, cookies, or logins. The Playwright CLI extension connection is the
only supported browser connection in this environment.

The installed extension supports multiple simultaneous clients. The wrapper
automatically assigns each Codex controller a session derived from
`CODEX_SESSION_ID`, producing a separate extension connection and tab group.
Non-Codex controllers can set `PLAYWRIGHT_CLI_SESSION` explicitly.

## Foreground opt-in

The wrapper defaults to background mode. `attach --extension` can reuse a verified
open attached session without a new handshake. A fresh attachment, `tab-new`,
`tab-select`, `open`, `recording-start`, and `show` require a leading
`--allow-foreground`. Use it only after the user explicitly permits that foreground
run, for example:

```bash
~/bin/playwright-cli --allow-foreground attach --extension
```

Exit 75 means the wrapper refused a focus-taking action. Pause that action; do not
retry with the flag on your own. The opt-in does not relax session ownership or
permit the alternative connection paths prohibited below.

The wrapper gates known commands, not arbitrary JavaScript. Do not call
`bringToFront()`, `window.focus()`, or other activation APIs from `eval` or
`run-code` during background work. Treat popup creation, native dialogs, and
unverified interaction paths as requiring coordinated foreground access.

Do not substitute another browser surface or controller for website automation:
do not use MCP browser tools, Computer Use, CUA, CDP, Selenium,
AppleScript/browser UI scripting, `open -a`/native GUI automation, a fresh
Playwright browser, or a different Playwright session. Do not attach without the
extension. Those paths can target the wrong profile and can replace or
desynchronize the user's attached tab. Computer Use is permitted only for
browser-chrome UI that the extension cannot access (for example
`brave://settings` or a native save dialog); keep all web-page work in this
controller's Playwright session.

## Non-negotiable connection path and ownership

```bash
~/bin/playwright-cli attach --extension
```

The wrapper at `~/bin/playwright-cli` supplies the Brave executable, extension
token, and controller-specific session name. Always invoke that exact wrapper path. Do not use a
globally installed `playwright-cli` binary or call Playwright directly. Attach
once per task; do not repeatedly attach in an attempt to find another session.

Operate only the session selected by the wrapper. Do not pass another agent's
session name, reuse its tab group, or detach its connection. Multiple agents may
work concurrently when each uses its own wrapper-selected session.

## Mandatory session check

Immediately after `attach --extension`, and before any tab selection,
navigation, snapshot, click, fill, or other browser action, run:

```bash
~/bin/playwright-cli list
~/bin/playwright-cli tab-list
```

Proceed when all of these are true:

1. The attach command succeeded during the current task.
2. `list` identifies the session named by the attach result as `status: open` and
   `browser-type: chrome (attached)`. The wrapper's diagnostic JSON may report
   `headed: false` for a valid extension attachment; this field is not an
   attachment or visibility check. The `(attached)` marker is required.
3. `tab-list` shows at least one tab from the extension-exposed Brave session.

The requested page does not need to be open already. After these checks pass,
reuse a matching tab when one exists; otherwise open the requested URL with
`tab-new` after foreground permission. A newly attached session that exposes only the extension Welcome tab
is sufficient: use `tab-new` to navigate independently.

Treat any of the following as a hard failure and perform no browser actions:

- a missing `(attached)` marker, an unknown session, or evidence that the
  session is fresh, hidden, or from an earlier task;
- no tabs are exposed by the attached extension session;
- evidence that the attached browser session is not the user's Brave profile or
  belongs to a different controller.

On a hard failure, do not navigate, open a replacement tab, log in, or claim to
see the user's browser. Report the connection problem without asking the user
to attach, drag, or open a particular tab.

If attachment fails, verify the extension and the token in
`~/.config/playwright-cli/env`, then stop and report the connection problem.
Never work around it by opening a new browser, using a hidden/headless browser,
or switching to another browser surface. Never ask the user to attach, drag, or
open a target tab. When attachment succeeds, open missing pages yourself.

## Work with tabs

- After the mandatory session check passes, run
  `~/bin/playwright-cli tab-list` again immediately before selecting a tab;
  reuse a matching tab. Tab selection and creation still require the foreground
  opt-in above; when it is not granted, pause those actions.
- `tab-list` is authoritative for the attached extension session. Do not infer
  that an OS-visible Brave window, another profile, or another browser session
  is the same target.
- Never proceed on a missing `(attached)` marker or an unverified session. Do
  not use `headed` alone to reject or accept an extension connection. The
  user's visible Brave profile must be the one attached through the extension.
- Select tabs only from a fresh `tab-list`; indexes can change.
- Run `~/bin/playwright-cli snapshot` before interacting, then use its refs for
  `click`, `fill`, `select`, and similar commands.
- After navigation, redirects, popups, or authentication, refresh both
  `tab-list` and `snapshot`. Reconfirm the session if the expected tab
  disappears or the session identity changes. Do not reuse stale refs.
- Run `~/bin/playwright-cli detach` when finished. The wrapper detaches only
  this controller's session; Brave, other controllers, and their tabs remain open.

## Guardrails

- Do not run `tab-close`, `close`, `close-all`, or `kill-all` during a task.
- Do not mix one controller's web-page work with an MCP browser, Computer Use,
  CDP, or another controller's named session. The narrow browser-chrome exception
  above does not authorize website interaction outside Playwright. Separate
  Playwright extension sessions are supported; sharing a session name is not.
- Never claim a particular tab is foreground-visible merely because it appears
  in `tab-list`; describe it as exposed by the attached Brave session.
- Keep sensitive values out of logs and snapshots.
- The wrapper redacts the extension token from command output. Never bypass the
  wrapper or print the token, full extension connection URL, or raw process
  command line.
- For purchases or other irreversible actions, stop at the final button and get
  confirmation immediately before clicking it.

Use `~/bin/playwright-cli --help` for the complete command reference.
Use `~/bin/playwright-cli doctor` for a read-only check of the Brave executable,
extension installation, token configuration, CLI version, session, and exposed
tabs.
