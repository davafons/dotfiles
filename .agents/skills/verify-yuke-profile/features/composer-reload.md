# Composer input and reload

## Sub-features

Vim motions, pending operators, draft/history precedence, completion, panel controls, and native reload cleanup.

## How to get to it (user POV)

Start Yuke, edit the composer in normal or insert mode, select a completion with Enter, open a panel, then reload after the run ends. Save the real draft before user-session reload.

## Driving it with the repository driver

Run the Drive command in SKILL.md. `check-profile.py` dispatches keys through the real composer, then sends Ctrl+G through its PTY. Both motion variants must complete and dispose two plugin generations.

## Gotchas

The reload fixture deliberately loses its private draft. This is not permission to reload the user. Fake transcript parts exercise history integration, not a real provider conversation.
