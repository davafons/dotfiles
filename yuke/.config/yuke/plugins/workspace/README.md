# Workspace commands

This profile plugin owns `/cd <path>` and `/pwd`. It uses only public Yuke interfaces. Session ownership and restoration stay in core.

Copy this folder to `plugins/workspace` in the profile and add `"./plugins/workspace"` to `config.json`. The native build must export `workspace` from `"yuke"`. Save unsent text and restart after a native update. Later plugin edits use `/reload` when idle.

`/pwd` reports the current workspace without changing history or drafts. Bare `/cd` reports the same path. `/cd <path>` forks committed history into the destination and reloads destination context. The original session stays unchanged. Matching outer quotes delimit the entire path without shell expansion.

The command requires one pane and the bundled shell. It refuses unfinished restoration, active or queued work, jobs, unrelated drafts, and attachments. An empty draft changes workspace without creating a session. The separate `path-completion` plugin supplies directory suggestions.

Without TUI, the plugin registers no commands. Removing its config entry removes both commands on reload. A failed profile boot preserves the destination through the core fallback, but profile commands return only after the profile loads again.
