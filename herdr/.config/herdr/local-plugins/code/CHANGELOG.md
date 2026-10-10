# Changes

## 2026-10-12

- Added a persistent Code tab per checkout and Herdr workspace, with a quick overlay sharing the same Neovim session.
- Added one-key return, checkout diffs, and an explicit recipient picker shared by questions and review comments. Opening from another agent does not retarget pending comments.
- Added pane, terminal and reported-session checks before delivery, including Yuke session tokens. Added unsaved-buffer recovery on owner shutdown without saving original files.
- Simplified the Vim workflow to `,ad` files/changes, `,aa` tag, `,as` send and `,at` choose recipient. Code starts with the checkout's existing file explorer. Each worktree keeps its own buffers, tags and recipient.
- Prevented stale overlay shutdown, failed opens and delayed focus events from replacing newer views. View generations remain distinct after closing and reopening Code.
- Tag delivery now always asks for a running Herdr agent, including `,as`, `,aS` and `:HerdrSend`. The searchable picker offers the last recipient first; Escape keeps queued tags. Choices are checked against the displayed conversation identity before delivery.
- Pinned worktree Code tabs at the left of the top bar, with the most recently opened or selected editor first. Tab events restore the group without changing pane focus, ordinary-tab order, buffers, tags or recipients. Added a startup hook and manual `david.code.pin` action.
- Code host panes, overlays and Neovim now open in the invoking checkout's canonical root. Pane launchers use the absolute plugin script, so a checkout's own `code.py` is never executed. This fixes the plugin-directory workspace name without modifying Herdr core.

- Changed the review shortcut to `Ctrl+a r`, with no Alt key required. Reviews open in the full Code tab, inline with the changed-file list hidden. `,b` shows the list and `t` switches to side-by-side. Both Herdr adapters use Neovim's review defaults.

Diffs show checkout changes, not agent-only attribution. Non-colocated jj workspaces support editing but need a Git-backed checkout for CodeDiff. The existing split-review plugin remains available.
