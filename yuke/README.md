# Personal Yuke profile

The canonical profile is `.config/yuke/config.json`. It lists 30 plugin folders with `plugin.json` manifests and default `apply(ctx)` entries. Yuke loads them at startup and through native `/reload`.

The installed migration build is `0.0.1-dev+e43023f2c5a7.b20261012130844`. It includes upstream `main` at `f9303882` and the retained personal APIs. The binary, library, and bundled profile match the verified release. A source checkout can have a later revision after documentation or history changes.

## Profile ownership

Keep credentials and mutable settings outside version control. The active profile is normally `~/.config/yuke`. Keep `providers.json` and `monid.key` as private regular files with mode `0600`. The installer owns `yuke.d.ts`, `yuke-modules.d.ts`, and `yuke.jsconfig.json`.

The initial cutover installed a copy of this profile. Editing this repository does not change that installed copy. Copy an intentional plugin edit into the active profile before `/reload`. Do not overwrite private settings. A native binary change needs a process restart.

Stow publishes only `.config/`. It excludes repository tests, historical guides, experimental code, and caches. A Stow install can conflict with the copied active profile. Resolve those conflicts deliberately. Do not use `stow --adopt` to overwrite the verified source with an older profile.

## Editing and navigation

The pinned [Vim plugin](.config/yuke/plugins/vim-mode/README.md) provides `composer-vim`. Its [source record](.config/yuke/plugins/vim-mode/SOURCE.md) identifies the imported revision. Logical-line `j` and `k` are the default. Set `verticalMotion` to `display` in `plugins/vim-mode/settings.json` for display-row motion. Operators retain logical-line ranges. `gj` and `gk` always use display rows. This profile omits `R` and retains native visual-put repeat. Yanks use OSC 52.

The empty-draft dashboard starts in normal mode. Its letters are `r` for sessions, `s` for search, `w` for work, `m` for models, `c` for commands, and `q` for quit. Press `i` to type. Nonempty drafts and open dialogs keep their own keys.

The profile keeps direct panel navigation, Ctrl+C handling, prompt history, path completion, model aliases, the Solarized theme, context and usage views, project work, clarification, sudo, web tools, Herdr, timers, and child-agent tools. Native MCP discovery remains enabled. Child tools preserve the configured `general` and `dav-agent` roles.

## Herdr agent reporting

The Herdr plugin starts reporting after `ui.started`, when the interactive frontend is ready. It reports again after native `/reload` and releases the pane on quit. `yuke check` and nested agents do not report over the parent pane.

After installing a plugin edit, wait for the active run to finish, save any typed draft, and run `/reload` in each Yuke session. Herdr does not need a server restart.

Run the regression against a private Herdr server and detached Yuke terminals:

```sh
python3 -B yuke/tests/check-herdr.py
```

The check uses temporary homes and stores. It does not copy provider credentials, make model calls, or touch live sessions.

## Verify the current profile

Run the complete profile guard from this repository:

```sh
python3 -B yuke/tests/check-profile.py \
  --binary "$HOME/.local/bin/yuke" \
  --types-dir "$HOME/.local/lib/yuke/types"
make check
```

The profile guard copies the canonical source into private homes. It checks exact types, startup, root input dispatch, native reload, two disposal generations, and headless startup in logical and display modes. It captures terminal output without a visible window. It does not forward OSC 52 or copy provider credentials. It makes no model call.

Current storage guards use disposable databases and files:

```sh
python3 -B yuke/tests/check-project-work-store.py
python3 -B yuke/tests/check-model-alias-store.py
python3 -B yuke/tests/check-yuke-clarify-store.py
python3 -B yuke/tests/check-search-store.py
```

These checks cover linked-checkout identity, concurrent version checks, private file modes, invalid-file preservation, clarification claims, index replacement, file boundaries, and bounded matching previews. They do not modify the active store.

`yuke check` runs plugin code and opens a store. Do not use the active profile for an isolated check. The installed guide at `~/.local/lib/yuke/docs/profile.md` gives the isolation recipe.

## Retired code and data

The old `index.js`, `profile.js`, factory plugins, and custom reload loader are no longer part of the canonical profile. The one-time migration command is retired. The cutover started a fresh session database. It did not import old chats. The operator approved deletion of the retired database, profile, and library after installed verification.

[Pre-manifest tests and guides](tests/pre-manifest/README.md) remain as reference material for later ports. They are not the current verification suite. The [loop plugin](LOOP.md) now uses manifests and native terminal-turn outcomes. The [Peek observer](.config/yuke/plugins/peek/README.md) makes separate tool-free model requests. Both entries are in the source configuration. The earlier installed 28-entry copy remains unchanged until a verified native build and these profile entries are installed.

The current candidate passes the full imported Vim invariant, search, and transcript checks. Editing parity matches real Vim in 581 cases. Transcript parity matches 48 cases. The 30-entry source profile passes types, startup, input, reload, disposal, and headless checks in both motion modes. See [Dashboard reuse](DASHBOARD.md) and [Work activity](WORK.md) for their checks.

Broader dialog and service checks and performance investigations remain open. The earlier allocation differences remain unexplained. The startup and input guards do not prove every external integration or paid-provider route. These candidate checks do not install or activate the source profile.
