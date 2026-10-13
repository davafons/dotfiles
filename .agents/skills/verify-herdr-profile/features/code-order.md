# Code-tab order and workspace identity

## Sub-features

Pin the owned Code group after ordinary tabs without changing the selected pane, custom workspace name, or saved routing records.

## How to get to it (user POV)

Open a Code tab with Ctrl+A E. Create, move, focus, and close tabs while preserving the project identity.

## Driving it with the repository driver

Run the Drive command in SKILL.md. The private stock Herdr instance exercises real create/move/focus/close hooks with fixture editor records. Read `code-order.json` after teardown.

## Gotchas

This proves ordering hooks, not full Code editor rendering or external comment delivery. The separate existing `code/tests/check-code.py` covers more editor integration and needs its own source/safety review before use. The multi-editor initial-order guard has shown an intermittent failure followed by a passing fresh-instance retry. Preserve failed snapshots and hook logs. A retry does not establish stability. Investigation is tracked as `w-b6d80bcefa2d4e20`.
