# Markdown rendering and preview split

## Sub-features

Inline rendering, hybrid insert editing, toggle, live preview of unsaved text, split position, focus preservation, and buffer-local mappings.

## How to get to it (user POV)

Open Markdown, use comma M P to toggle rendering, and comma M S to open or close the right preview split. Edit the source without saving.

## Driving it with the repository driver

Run `python3 -B "$NVIM_CONFIG/tests/check-markdown.py" 2>&1 | tee "$EVIDENCE/markdown.log"`. Require `Markdown checks passed` and zero exit. It sends real Neovim input and checks live extmarks, split contents, focus, and unchanged source on disk.

## Gotchas

This headless drive proves Markview behavior, not Ghostty graphics or the separate mcat launcher. Native GUI and relative-image proof remain separate gates.
