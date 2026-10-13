# Project pickers and command-line completion

## Sub-features

Project-root file/search pickers, Tab completion without submission, cancellation, search highlights, and the shortcut guide preserving edits.

## How to get to it (user POV)

Use comma F F or comma Space to find files. Use comma slash to search the project. Type a command or file path after colon, press Tab to complete, then Escape to cancel.

## Driving it with the repository driver

Run the Drive command in SKILL.md. `check-config.py` uses the existing PTY probe, actual fzf terminal selection, and Neovim input. Require its explicit completion report.

## Gotchas

The driver requires installed blink/fzf and real plugins. Its fake `.jj` directory only supplies root detection. This is not a repository-history verification.
