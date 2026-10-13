# Changes

## 2026-10-12

- Label owned editor tabs `Code` and report their editor role. Keep pinned editors out of checkout metadata selection. Keep Code tabs last through the stock tab-move API, so ordinary tabs supply automatic workspace identity without a native patch.

- Replaced all Alt-only shortcuts in the Mac Herdr configuration. After Ctrl+a, F1–F10 select tabs 11–20, Ctrl+Shift+F1–F10 select agents 11–20, and Shift+F1–F10 select workspaces 11–20. Existing 1–10 shortcuts are unchanged.
- Moved scrollback editing to Ctrl+a, then Ctrl+e. The Code tab, overlay and review keep e, Shift+e and r.
- Added real terminal dispatch coverage for every function-key bank in three input protocols, the unchanged 1–10 banks, and scrollback editor invocation and cleanup.
