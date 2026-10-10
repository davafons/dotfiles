# Context dashboard

`context-dashboard` replaces the built-in `/context` popup in this profile. It keeps the built-in context status bar. It adds no model tools, request hooks, or stream listeners.

Restart Yuke after installing the core update for tool inspection. Then run `/context`. Later profile-only changes can use `/reload`. An older executable still shows prompt and skill data, but the Tools tab reports that inspection needs the update.

## Overview

The window shows the selected chat's model, occupied context, and a 200-square grid. Wide dialogs place the grid in a left column and the legend in a right column. Narrow dialogs stack them, with the grid using the full available width. The layout adjusts when the dialog resizes. Each square represents about 0.5% of the model window. Press `v` to scale the same grid to the saved prompt budget instead. This makes small upfront costs visible. The legend still gives shares of the full model window. Colors identify these categories:

| Category | Color | Meaning |
|---|---|---|
| System + plugin instructions | Violet | Base prompt, environment, and other prompt sections |
| AGENTS.md instructions | Blue | Stored global and workspace instructions |
| Skill catalog | Yellow | Skill summaries and paths, not full skill bodies |
| Tools / request overhead | Cyan | Remaining fixed request estimate after the stored system prompt |
| Chat + tool results + reasoning | Green | Occupied context minus the fixed request estimate |
| Free until auto-compaction | Muted outline | Room before the engine's compaction threshold |
| Remaining safety reserve | Warning hatch | Unused room above that threshold |

The legend gives token estimates and percentages even when a category is too small to occupy one square. The grid uses largest-remainder rounding. It does not give every category a minimum square. An overfull context fills the grid and shows the excess.

## Details

The Details tab shows the model window, compaction threshold, safety reserve, message and queue counts, pending compaction, last reported token/cache counts, session token totals, known API cost, saved prompt sections, instruction paths, and the stored skill catalog.

The view reads a snapshot when it opens. Press `r` to read it again. It does not poll during a run.

## Skills and Tools

The Skills tab lists each summary's UTF-8 byte size, token estimate, and percentage of occupied context. The summary includes the skill name, description, path, and XML markup. A separate row holds the catalog header and separators. The helper measures the actual saved prompt text, not the current skill file. Row estimates and header overhead add up to the skill section estimate. A custom prompt with no recognizable summary has an unknown per-skill cost.

The Tools tab lists current registered definitions, largest first. Each row shows potential token cost, estimated bytes, and percentage of occupied context. A second line separates the exact description and compact JSON schema sizes. The token estimate includes the engine's 128-byte framing estimate. Inspection runs no handlers, selection predicates, or engine hooks.

The tool catalog is not a record of the last request. Hooks can omit or replace definitions. A deferred tool or variant need not enter a request. Tool responses and loaded skill bodies remain in the chat category; these tables do not attribute those bytes to a skill or tool.

## Controls

- `1`, `2`, `3`, and `4` select Overview, Details, Skills, and Tools.
- Tab, Shift+Tab, Left, and Right switch tabs.
- `j`/`k`, Up/Down, PageUp/PageDown, Home/End, and the mouse wheel scroll.
- Click a tab to select it.
- `v` switches the Overview grid between the whole window and the saved prompt budget.
- `r` refreshes the snapshot.
- Escape, Ctrl+C, and `q` close the window.

Opening or closing the view preserves the composer draft. The dialog owns its reader. Closing or unloading it cancels that reader and ignores late replies. Unloading the plugin restores the built-in `/context` command.

## Counts and limits

The occupied total comes from `session.get`. The engine anchors that count in provider usage, then estimates later messages. Cached input still occupies context.

The category split uses Yuke's existing estimate of one token per four UTF-8 bytes. It is not a provider tokenizer count. `context-data.py` reads saved prompt metadata in one read-only SQLite transaction. It reads neither transcript bodies nor skill bodies.

Yuke does not save the declarations or count of tools in each request. The tools row is the residual of the last fixed request budget after the stored system estimate. Request overrides can also enter that residual. Loaded tool definitions that arrive later through discovery belong to the chat remainder. The Tools tab uses `ctx.tools.inspect()` for the current registered definitions. It does not treat historical calls as currently loaded definitions or claim that the catalog explains the entire saved residual.

After reload marks a prompt stale, the grid keeps the saved prompt estimates. It labels them as saved sizes and leaves unknown tools in the chat remainder. A changed model or missing budget can leave full attribution unavailable. No category gets a negative remainder. When saved prompt costs exceed occupied context, the grid leaves all occupied context unattributed. A fresh draft has no saved request breakdown. An unknown model window has no percentage grid or reserve estimate.

The safety reserve follows the engine formula: the larger of 10% of the window and the smaller of 16,384 tokens or 25% of the window. It is not a separate count of completed reasoning or a guaranteed reply size.

The command loads `context-view.js` only when it opens. An unused dashboard does not load its view or category code. Rows and grid cells rebuild only on a read, tab change, or resize. Drawing reads cached spans. The plugin uses the theme palette in truecolor and 256-color terminals, in dark and light mode.

## Reuse

Copy `context-dashboard.js`, `context-view.js`, `context-model.js`, and `context-data.py` into the profile's `plugins` directory. Import `contextDashboard` and register it with `ctx.use(contextDashboard)`. The helper requires Python 3 and the current Yuke session-store schema. No Python package is required.

## Verification

```sh
node ~/.config/yuke/tests/check-context-model.mjs
PYTHONDONTWRITEBYTECODE=1 python3 ~/.config/yuke/tests/check-context-data.py
python3 ~/.config/yuke/tests/check-context-tui.py
python3 ~/.config/yuke/tests/check-context-tui.py --colors truecolor --background light
python3 ~/.config/yuke/tests/check-context-tui.py --colors 256 --background dark
python3 ~/.config/yuke/tests/check-context-tui.py --colors 256 --background light
python3 ~/.config/yuke/tests/check-context-tui.py --full-profile
tsc -p ~/.config/yuke/jsconfig.json
yuke check
```

The TUI test uses isolated stores, a loopback provider, and a detached tmux session. It checks category colors, prompt-only grid scaling, per-skill and per-tool costs, retention of saved prompt categories after reload invalidation, budget details, refresh without a model call, draft preservation, resizing, unload/reload, and restoration of the built-in command. It saves text and ANSI captures. It never attaches to the user's terminal or accesses the clipboard.

## Performance

The first version loaded the view at startup. It added about 101–120 KiB of resident memory in closed-view workloads, so the command now loads its view on first use. A comparison of the lazy plugin against no dashboard used five alternating timing runs and two allocation-slope windows. Closed-view frame, streaming, and input times differed by less than 0.3%, within noise. Frame allocations stayed at zero. Input stayed at two allocations and 144 bytes per iteration. Streaming differences changed direction between windows. The lazy command added about 7–15 KiB of resident memory in those runs.

That comparison preceded the core inspection API. The first API comparison reported a 33% slower frame phase, with wide sample variation while tests and builds overlapped. A nine-run alternating confirmation did not reproduce it: frame −0.25%, streaming +0.09%, and input +0.13%, all within wall-time noise. The confirmation asserts that measured phases never read the tool-registry getter. Frame stayed at zero allocations and input at two allocations and 144 bytes per iteration in both windows. Streaming differs by about 0.01 and 2.73 allocated bytes per iteration across the two windows; exact streaming allocation equality is not established. The closed plugin and API add about 14.5 KiB of resident memory.

Retained reports are `/tmp/context-dashboard-bench-8vpe6aq2` and the earlier noisy comparison `/tmp/context-dashboard-bench-hg3rq597`. Core API runtime files remain unchanged from that earlier snapshot. The confirmation covers the lazy command and closed view, not opening, painting the active modal, or retention after its first use. Overview layout changes only affect cached rows and columns. Callgrind is unavailable, so these results do not prove an exact instruction count. Installed-build TUI and type checks pass; existing processes need a restart for the tool API.
