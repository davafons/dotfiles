# Changelog

## Unreleased

- `/sessions` now marks sessions mapped to another Herdr pane in cyan (`↗ ELSEWHERE`). Click the row or press Enter to jump to its owning pane instead of trying to resume it locally. Sessions with no reported pane remain protected.

- Added the running Yuke build to the bottom status bar. The label comes from the engine's embedded version, so installing a new binary does not make an old process appear current. Local builds now include the source revision and UTC build time.

- Percentage breakdowns in `/usage` now use parentheses, for example `1,180,000 (79.7%)`, instead of a dot separator.

- Added consumption percentages to `/usage`: cache reads/writes and uncached input as shares of input, input/output as shares of total tokens, reasoning as a share of output, and cache savings relative to estimated no-cache cost. Provider/model and period tables show weighted cache-read rates.

- Added semantic colors to `/usage`: blue headings and navigation, cyan token counts and tools, violet reasoning and skills, green savings and healthy states, amber costs and incomplete data, and red failures. Chat metadata is split into colored fields.

- Added `/usage`, a Codex-style dashboard with six tabs, a yearly token heatmap, global/workspace filtering, token and cost breakdowns, provider/model statistics, tool and skill rankings, and searchable chats with resume controls.
