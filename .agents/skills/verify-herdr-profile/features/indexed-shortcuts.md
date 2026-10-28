# Indexed shortcuts and scrollback

## Sub-features

Tab, agent, and workspace function-key banks, position 10, missing-position focus guards, and scrollback editor dispatch.
The sidebar plugin's client companion also covers one number sequence across
machines, machine ordering, stale metadata, offline entries, and global tab badges.

## How to get to it (user POV)

Use Ctrl+A then the numbered/function-key bank for tabs, agents, or workspaces. Use Ctrl+A Ctrl+E to open focused-pane scrollback.

## Driving it with the repository driver

Run `python3 -B "$HERDR_GUARDS/sidebar-numbers/tests/check-shortcuts.py" 2>&1 | tee "$EVIDENCE/shortcuts.log"`. Require all printed PASS lines and zero exit. Its private tmux server sends legacy, CSI-u, and SS3/CSI sequences.

For the companion, run `build-client.py` with Python 3.14 and Zig 0.16 available.
Its `client::shell::` tests include the `sidebar_numbers` regression group:
two simulated endpoint snapshots deliberately reuse IDs, and real client
composition and key dispatch verify the combined order. This does not establish
SSH connectivity to Tower. Run the shortcut driver with the built binary first
on `PATH`; it copies the checked-in config into its private session.

## Gotchas

The editor is a private capture executable, not the user editor. Fixture state is removed after the drive, so retain stdout as evidence. This does not prove physical keyboard encoding in the user terminal.
