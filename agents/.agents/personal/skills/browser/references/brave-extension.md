# Local Brave extension backend

Drive David's Brave Beta through `~/bin/playwright-cli`, never the global
`playwright-cli` binary. Each activity is its own background tab group in his
profile:

```bash
~/bin/playwright-cli --activity=shopping attach --extension
~/bin/playwright-cli --activity=shopping goto https://example.com
~/bin/playwright-cli --activity=shopping snapshot
```

Activity names are lowercase slugs of at most 40 characters. Reuse one name
throughout a flow and use separate names for parallel stateful work. Attaching
again reuses the live group.

The wrapper names the session from `CODEX_SESSION_ID` or `CLAUDE_CODE_SESSION_ID`.
Other controllers set a unique `PLAYWRIGHT_CLI_SESSION` on every call: Yuke uses
`yuke-<current-session-id>`, kept for the whole chat and never stored as a
shared default. Never pass `-s`/`--session` or fake a session ID. Pass
`DAVAFONS_BROWSER_BACKEND=brave-extension` when the backend came from the
private configuration rather than the environment.

Run `~/bin/playwright-cli <command> --help` for syntax. The official skill's
workflow guides (tracing, request mocking, storage state, running code) are in
[playwright-cli/](playwright-cli/); read one only when the task needs it.
`open`, `close`, `detach` and session flags are replaced by `attach --extension`
and `--activity`.

Attaching and all later commands run in the background, including clicks and
typing in inactive tabs. When David says an activity is done, run
`detach --close-tabs` for it. The
wrapper pins the CLI and patches focus emulation for that (microsoft/playwright
#44096). If background input breaks, verify on a test page before adding window
management or bypassing click stability checks.

For checking an app you are developing locally, use the project's own headless
Playwright (its system tests or screenshot script), not this backend.

## Work

Take a fresh snapshot before interacting, and again after navigation,
redirects, authentication, or a popup. Use absolute paths for uploads, scripts,
and named artifacts. For debugging, use `console`, `requests`, `request`,
`eval`, and tracing in the affected tab; do not open native DevTools.

## Boundaries

Do not use raw CDP, Selenium, a browser MCP, AppleScript, Computer Use, CUA,
`open -a`, or a fresh Playwright browser for web-page interaction. Computer Use
is allowed only for browser chrome that the extension cannot reach. Do not
create another window or minimize Brave.

Never print the extension token, connection URL, or raw browser command line.
`~/bin/playwright-cli doctor` is a read-only configuration check.
