# Local Brave extension backend

Use David's existing Brave profile through the exact wrapper:

```bash
~/bin/playwright-cli --activity=shopping attach --extension
~/bin/playwright-cli --activity=shopping list
~/bin/playwright-cli --activity=shopping tab-list
```

The wrapper supplies the Brave executable, token, and a controller-specific
session derived from the full `CODEX_SESSION_ID` plus an activity name. Activity
names are unique lowercase slugs of at most 40 characters. The extension
creates a distinct visible group named `Codex <short-id> · <activity>`. Reuse
the same short activity name for every command in one flow. Use separate
activities when one agent needs parallel stateful browsing:

```bash
~/bin/playwright-cli --activity=product-a ...
~/bin/playwright-cli --activity=product-b ...
```

Never pass another session name or use the global `playwright-cli` binary
directly. A non-Codex controller must set its own unique
`PLAYWRIGHT_CLI_SESSION`; the wrapper does not fall back to a shared
working-directory session. Changing repositories cannot create another group
for the same controller/activity. Use absolute paths for uploads, scripts, and
named artifacts.

The wrapper-selected session—not the visible label or color—is the ownership
boundary.

Commands for one controller/activity are serialized with a lightweight local
file lock. Different controller IDs and different activities use different
locks and continue in parallel; never reuse another agent's activity.

## Focus and visibility

The stock Playwright extension activates Brave when a fresh token connection is
created. The wrapper therefore requires `--allow-foreground` for a fresh attach,
tab creation, tab selection, recording UI, or the visual dashboard. Foreground
browser work is allowed by default when the task requires it:

```bash
~/bin/playwright-cli --allow-foreground --activity=shopping attach --extension
```

Exit 75 means the action was refused. Reusing an already attached session does
not create another handshake tab. Prefer commands that do not change focus when
they are sufficient, but do not pause merely to request foreground permission.

These groups intentionally share David's normal Brave window and profile.
AeroSpace manages windows, not tab groups, so do not move or create a separate
Brave window for an agent. A different Chromium profile would necessarily use
a different window and is not part of this backend.

Keep the browser visible and in its normal state. Do not minimize it, replace it
with a headless browser, or use a hidden fallback. David may open the agent's
group to observe it. If he needs to interact or log in, stop issuing commands
until he hands the tab back.

## Verify ownership

Immediately after attaching, run `list` and `tab-list`. Proceed only when:

1. `list` contains exactly this wrapper-selected session with `status: "open"`,
   `browserType: "chrome"`, and `attached: true`.
2. `tab-list` exposes at least one tab in this controller's group.
3. There is no evidence that the session or tab belongs to another controller.

Do not infer ownership from the OS-visible window or the active tab. The
wrapper-filtered session and `tab-list` are authoritative.

## Work in parallel

Ordinary `goto`, snapshot, click, fill, evaluation, console, request, and trace
commands operate on the session's current page and can run while David uses a
different group. Prefer navigating the existing page over creating or selecting
tabs. Treat links that open a popup or new tab as foreground-capable operations.

Before interacting, take a fresh snapshot. Refresh `tab-list` and the snapshot
after navigation, redirects, authentication, or a popup. Never reuse stale refs.

For debugging, use `console`, `requests`, `request`, `eval`, and tracing in the
owned tab. Do not open native DevTools through UI automation.

Keep the session attached after reporting results so David can inspect the page
and follow-up requests can continue in the same activity and tab. Do not infer
that an activity is done merely because the current request was answered.
Detach only when David explicitly says the activity is done or asks to detach
it. Detaching affects only this controller; never run `tab-close`, `close`,
`close-all`, or `kill-all`.

## Prohibited alternatives

Do not use raw CDP, Selenium, a browser MCP, AppleScript, Computer Use, CUA,
`open -a`, or a fresh Playwright browser for web-page interaction. Computer Use
is allowed only for browser chrome that the extension cannot reach.

Do not call `bringToFront()`, `window.focus()`, or activation APIs through
`eval` or `run-code`. Never print the extension token, connection URL, or raw
browser command line.

Use `~/bin/playwright-cli doctor` for a read-only configuration check.
