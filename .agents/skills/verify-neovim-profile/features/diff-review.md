# Diff review and unsaved edits

## Sub-features

Inline/full-width layout, hidden file list, file/hunk navigation, layout and folding toggles, and closing without saving edits.

## How to get to it (user POV)

Use comma J D in a jj checkout. Use bracket C for hunks, bracket F for files, T for layout, comma B for the file list, G C for compact mode, and Q to close.

## Driving it with the repository driver

Run `python3 -B "$NVIM_CONFIG/tests/check-diff.py" 2>&1 | tee "$EVIDENCE/diff.log"`. Require `Neovim diff checks passed` and all returned guards. It creates its own jj fixture and presses the actual mappings.

## Gotchas

Only the fixture jj history is mutated. No staging, push, or real checkout edits occur. A successful layout probe is not pixel-parity evidence.
