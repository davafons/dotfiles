# Local Brave extension backend

Use David's existing Brave profile through the exact wrapper:

```bash
~/bin/playwright-cli --activity=shopping attach --extension
```

Attach verifies the controller-owned session and tab group before returning.
The wrapper supplies the Brave executable and token, serializes commands per
activity, and derives an isolated session from `CODEX_SESSION_ID`. Activity
names are lowercase slugs of at most 40 characters. Reuse one name throughout a
flow and use separate names for parallel stateful work:

```bash
~/bin/playwright-cli --activity=product-a ...
~/bin/playwright-cli --activity=product-b ...
```

Never pass a session name or invoke the global `playwright-cli` binary. A
non-Codex controller must set a unique `PLAYWRIGHT_CLI_SESSION` on every call.
For Yuke, use `yuke-<current-session-id>`, substituting this chat's actual session
ID. Reuse that value for this chat, including across tool calls, and never store
it as a shared profile default. If the ID is unavailable, generate a UUID once
and retain it for this chat. Pass `DAVAFONS_BROWSER_BACKEND=brave-extension`
when the backend was resolved from the wrapper's private configuration rather
than inherited. Do not set a fake `CODEX_SESSION_ID`.

Use absolute paths for uploads, scripts, and named artifacts.

The groups share David's normal Brave profile but remain separate tab groups.
Do not create another browser window, minimize Brave, or substitute a headless
browser. Reattaching reuses the existing group.

## Work

Prefer the existing page, but use new tabs, popups, and tab selection when the
task requires them. Before interacting, take a fresh snapshot. Refresh the tab
list and snapshot after navigation, redirects, authentication, or a popup.

For debugging, use `console`, `requests`, `request`, `eval`, and tracing in the
affected tab. Do not open native DevTools through UI automation.

## Boundaries

Do not use raw CDP, Selenium, a browser MCP, AppleScript, Computer Use, CUA,
`open -a`, or a fresh Playwright browser for web-page interaction. Computer Use
is allowed only for browser chrome that the extension cannot reach.

Never print the extension token, connection URL, or raw browser command line.
The wrapper disables browser-closing commands. Use
`~/bin/playwright-cli doctor` for a read-only configuration check.
