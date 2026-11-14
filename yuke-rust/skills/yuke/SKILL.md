---
name: yuke
description: Customize the installed Yuke coding agent through its profile, plugins, tools, hooks, commands, keys, widgets, providers, and models. Use for profile changes and plugin loading failures.
---

# Customize Yuke

Run `yuke --version` before choosing declarations.
The personal default is Rust Yuke with `YUKE_APPNAME=yuke-rust`.
Its profile is `$XDG_CONFIG_HOME/yuke-rust`, normally `~/.config/yuke-rust`.
Its canonical source is `~/dotfiles/yuke-rust/.config/yuke-rust`.
Its public SDK is `~/.local/lib/yuke-rust`.
Its native source is `~/workspace/yuke`.

Read the exact public declaration in the SDK's `types/` or `modules/` before editing.
Read `docs/personal-plugins.md` in the native source for the added chat, record, inspection, fork, tool selection, and geometry operations.
Use only public `yuke:` imports.
Put manifest fields under `extensions["sh.yuke"]` in `plugin.json`.
Register model tools and session hooks in the `session` export.
Register UI operations in `apply` after checking `ctx.get("tui")`.
A headless host has no TUI.
Keep plugin resources bound to their context, widget, dialog, or session signal.

Edit the canonical dotfiles profile, then run:

```sh
python3 ~/dotfiles/yuke-rust/tests/typecheck.py --source ~/workspace/yuke
python3 ~/dotfiles/yuke-rust/scripts/verify.py --source ~/workspace/yuke --binary ~/.local/lib/yuke-rust/bin/yuke
```

The installed profile links to the canonical files through Stow, so edits apply after `/reload`.
Run `make install PROFILE=mb` from `~/dotfiles` after adding or removing a profile file.
That also runs `scripts/setup-state.py`, which only creates missing state and never replaces it.
`providers.json` is tracked and holds no credentials. Keep `auth.json` and `monid.key` private.
Never print their values.
Rust stores credentials in `$XDG_DATA_HOME/yuke-rust/auth.json`.
Its session IDs are hyphenated UUIDs.
Native session folders use the UUID's 32 hexadecimal digits.

A native binary change needs a restart.
Wait for active work before `/reload`.
Check UI changes in a private terminal using `tests/terminal.py`.
That test uses no credentials or external model requests.

