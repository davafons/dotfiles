# Provider status

`/status` opens a compact status card for the selected chat and provider. Account allowance comes first. The default view shows the model, plan, reasoning effort, remaining allowances, credits, context space, and session token total. Press `d` for authentication, workspace, session ID, activity, build, AGENTS.md paths, token breakdown, and known API cost.

This profile enables the plugin. Use `/reload` or restart Yuke to load it. No executable update is required. The profile's custom `/reload` loader reads plugin changes; the standard Yuke loader requires a restart.

## Account limits

| Provider | Reported data |
|---|---|
| `openai-codex` | Account plan, remaining timed allowances, reset times, additional model-specific limits, and credits when present |
| `openrouter` | Remaining API-key spending cap and free-model daily requests when present |
| Other providers and custom routes | Account quota unavailable; no invented balance |

Codex windows use the duration in the response. A primary window can be weekly, not 5-hour. The card labels 5-hour and weekly windows only when the provider reports those durations. It shows a zero allowance. It does not treat an absent window as full, exhausted, or unlimited.

Codex credits are credits, not tokens. OpenRouter's key cap is not the account credit balance. A missing key cap does not mean unlimited funds. Neither adapter reports an exact remaining-token count. `/status` states that limit rather than deriving one from prices, session totals, or context space.

The context count combines the last provider count with the engine's estimate of later messages. Context space is room within the model window, not account allowance or a guarantee that the next request fits. Session usage sums completed replies. Cached tokens remain in input totals. Unknown reply prices remain unpriced, not free.

The card does not recreate Codex's sandbox or approval policy. Yuke does not use that policy. A fresh draft has no saved session usage or saved reasoning effort. If a running turn uses a different model from the next turn, Details shows both models.

## Layout and colors

The card fits its content instead of filling the terminal. Blank rows separate allowance bars from credits, context space from session usage, and the diagnostic groups. Solid Unicode bars show remaining allowance and free context space. Partial blocks give one-eighth-cell precision. An exhausted allowance has an empty track; a full allowance has a full bar. Unknown allowances have no bar.

Account bars are green above 25%, amber at 11–25%, and red at 10% or less. Context space uses cyan. Empty tracks and supporting text use the theme's readable muted color. The model, plan, section headings, and numeric values have separate colors. The card follows the palette in truecolor and 256-color, in dark and light mode.

The default view omits the missing-5h notice and credit explanations. The footer shows colored refresh, details, and close hints without `j/k`. `d` shows the full diagnostics and provider notes. Details uses violet for models, green for ready authentication, cyan for token counts, and amber for unpriced costs. The card resizes when details open or close. Narrow terminals retain scrolling.

## Controls

- `d` shows or hides details.
- `r` reads a new snapshot.
- Up/Down, PageUp/PageDown, Ctrl+D/Ctrl+U, Home/End, and the mouse wheel scroll.
- Escape, Ctrl+C, and `q` close the card.

Opening and closing the card preserve the composer draft. The snapshot stays with the chat that opened it. Close and reopen it after switching chats. Refresh reads that chat's current selected model and provider. The view does not poll during a run.

Quota failures remain visible with the session fields. A failed refresh removes the previous quota values, so old allowances do not appear current. Press `r` to retry. Closing or unloading cancels the reader and ignores late output.

## Credentials and requests

`status-data.py` reads the profile's private `providers.json`. It uses Yuke's stored Codex OAuth access token and account ID. OpenRouter accepts its configured literal key or environment variable; with no override it uses `OPENROUTER_API_KEY`. An explicitly empty configured key does not fall back to that variable.

The reader makes one read-only GET to a fixed official endpoint:

- Codex: `https://chatgpt.com/backend-api/wham/usage`
- OpenRouter: `https://openrouter.ai/api/v1/key`

It sends no model request. It does not refresh a login, reset an allowance, purchase credits, or write credentials. It rejects redirects and custom base routes. It does not print request headers, tokens, account IDs, or error bodies. Configuration and response reads have a 256 KiB limit. The network timeout is 10 seconds. The owning command cancels the helper after 15 seconds or on close.

An expired Codex grant needs Yuke's normal login refresh or `/login openai-codex`. The status reader does not run a competing refresh. After a manual provider-file edit, use `/reload-providers` so the active engine and file agree. Authentication in the card comes from the engine catalog; quota credentials come from the stored file. This plugin does not read Codex CLI's separate login store.

The Codex endpoint comes from [Codex's backend client](https://github.com/openai/codex/tree/main/codex-rs/backend-client/src). It is an account backend endpoint, not a stable public OpenAI API. A server change can make the reader unavailable. OpenRouter documents [key limits](https://openrouter.ai/docs/api_reference/limits). Its account-credits endpoint requires a management key, so this plugin does not request it with a model API key.

## Reuse

Copy `status.js`, `status-view.js`, and `status-data.py` into the profile's `plugins` directory. Import the plugin in the profile:

```js
import { status } from "./plugins/status.js";
```

Register it inside the profile plugin's `apply(ctx)`:

```js
ctx.use(status);
```

The helper requires Python 3. It requires no Python package. The command loads the view only on first use. It adds no model tools, stream listeners, per-frame status items, or request hooks. The view builds rows on reads and resize. Drawing reads cached rows.

## Verification

```sh
PYTHONDONTWRITEBYTECODE=1 python3 ~/.config/yuke/tests/check-status-data.py
PYTHONDONTWRITEBYTECODE=1 python3 ~/.config/yuke/tests/check-status-tui.py
PYTHONDONTWRITEBYTECODE=1 python3 ~/.config/yuke/tests/check-status-tui.py --full-profile
PYTHONDONTWRITEBYTECODE=1 python3 ~/.config/yuke/tests/check-status-tui.py --colors truecolor --background light
PYTHONDONTWRITEBYTECODE=1 python3 ~/.config/yuke/tests/check-status-tui.py --colors 256 --background dark
PYTHONDONTWRITEBYTECODE=1 python3 ~/.config/yuke/tests/check-status-tui.py --colors 256 --background light
tsc -p ~/.config/yuke/jsconfig.json
yuke check
PYTHONDONTWRITEBYTECODE=1 python3 ~/.config/yuke/tests/check-status-perf.py --repo /path/to/yuke
```

The helper tests pin window meaning, additional limits, zero allowances, missing and invalid fields, key-cap meaning, credential routing, expiry, private-file checks, and secret-free failures. The detached-TUI test uses isolated stores, dummy credentials, a loopback model, and the real quota reader with a fixture transport. It checks the compact card, full/empty Unicode bars, actual ANSI foreground colors, details toggle, slash command, session counts, provider changes, errors, retry, draft retention, narrow layouts, scrolling, unload/reload, cancellation, and fresh drafts. It makes one loopback model call to seed the session. Status operations make none. It saves labeled captures. It does not attach to a terminal, activate an app, or use the clipboard.

The performance test compares the lazy command with no command in scratch copies of the supplied Yuke source. It uses five alternating timing runs, the lowest quartile, and two separate allocation-slope windows. It measures an unopened command, not the active modal or retention after first use. It deletes only its scratch build trees and keeps the reports.

## Performance results

The unopened command comparison measured frame time at -0.08%, stream time at +0.13%, and input time at +4.47%. A confirmation used nine alternating input runs at 6,000 iterations and measured -2.29%. The initial input slowdown did not repeat. These differences fall within the measured timing noise; they do not prove a speedup or zero instruction cost.

Both allocation-slope windows kept frame drawing at zero allocations and zero bytes. Input stayed at two allocations and 144 bytes per iteration. Streaming bytes differed by -2.72 bytes per iteration in the first window and +5.456 in the second. Those differences change direction, so the comparison does not prove exact streaming allocation equality.

The lazy registration added about 10.6–18.6 KiB of live memory in these workloads. The wrapper hash stayed the same across the compact UI revision and both comparisons. The comparisons did not open the view. Active-modal time and memory retention after first use remain unmeasured. Callgrind was unavailable.

Repeat an input confirmation with:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 ~/.config/yuke/tests/check-status-perf.py --repo /path/to/yuke --phase input --runs 9 --iterations 6000 --time-only
```
