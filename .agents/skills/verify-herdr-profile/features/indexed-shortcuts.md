# Indexed shortcuts and scrollback

## Sub-features

Tab, agent, and workspace function-key banks, position 10, missing-position focus guards, and scrollback editor dispatch.

## How to get to it (user POV)

Use Ctrl+A then the numbered/function-key bank for tabs, agents, or workspaces. Use Ctrl+A Ctrl+E to open focused-pane scrollback.

## Driving it with the repository driver

Run `python3 -B "$HERDR_GUARDS/sidebar-numbers/tests/check-shortcuts.py" 2>&1 | tee "$EVIDENCE/shortcuts.log"`. Require all printed PASS lines and zero exit. Its private tmux server sends legacy, CSI-u, and SS3/CSI sequences.

## Gotchas

The editor is a private capture executable, not the user editor. Fixture state is removed after the drive, so retain stdout as evidence. This does not prove physical keyboard encoding in the user terminal.
