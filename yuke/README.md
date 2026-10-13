# Personal Yuke profile

The canonical profile is `.config/yuke/config.json`. It lists local plugin folders and GitHub sources with `plugin.json` manifests and default `apply(ctx)` entries. Yuke loads them at startup and through native `/reload`.

Solarized and the empty-session dashboard load from `lostcoords/yuke-plugins`, not copied folders in these dotfiles. Each source entry pins the published commit in `ref`. Change that value to select another version. Keep `.plugin-cache/` out of version control. The other plugins keep their existing local entries.

The initial migration used `0.0.1-dev+e43023f2c5a7.b20261012130844`, including upstream `main` at `f9303882` and the retained personal APIs. Later native installs can have a different build identity. Keep the binary and installed SDK matched. A source checkout can have a later revision after documentation or history changes.

## Profile ownership

Keep credentials and mutable settings outside version control. The active profile is normally `~/.config/yuke`. Keep `providers.json` and `monid.key` as private regular files with mode `0600`. The installer owns `yuke.d.ts`, `yuke-modules.d.ts`, and `yuke.jsconfig.json`.

The initial cutover installed a copy of this profile. Editing this repository does not change that installed copy. Copy an intentional plugin edit into the active profile before `/reload`. Do not overwrite private settings. A native binary change needs a process restart.

Stow publishes only `.config/`. It excludes repository tests, historical guides, experimental code, and caches. A Stow install can conflict with the copied active profile. Resolve those conflicts deliberately. Do not use `stow --adopt` to overwrite the verified source with an older profile.

## Editing and navigation

The pinned [Vim plugin](.config/yuke/plugins/vim-mode/README.md) provides `composer-vim`. Its [source record](.config/yuke/plugins/vim-mode/SOURCE.md) identifies the imported revision. Logical-line `j` and `k` are the default. Set `verticalMotion` to `display` in `plugins/vim-mode/settings.json` for display-row motion. Operators retain logical-line ranges. `gj` and `gk` always use display rows. This profile omits `R` and retains native visual-put repeat. Yanks use OSC 52.

The empty-draft dashboard loads from the pinned GitHub commit. `dashboard-config` calls `setup` with the rows. The letters are `l` for sign-in, `r` for sessions, `s` for search, `w` for work, `m` for models, `c` for commands, and `q` for quit. Those letters run only while the draft is empty. Any other character starts the prompt.

The profile keeps direct panel navigation, Ctrl+C handling, prompt history, path completion, model aliases, the Solarized theme, context and usage views, project work, clarification, sudo, web tools, Herdr, timers, and child-agent tools. Native MCP discovery remains enabled. Child tools preserve the configured `general` and `dav-agent` roles. The `reviewer` role selects `openai-codex/gpt-6.1-sol` at `xhigh` for fresh non-author review. Spawn results include engine-accepted model and effort receipts. Child requests log their selected model. Codex-only review does not satisfy a different-model-family requirement. See the [child-tools guide](.config/yuke/plugins/agent-tools/README.md).

## Feature settings

`models`, `controls`, `run-feedback`, and `insights` each read optional `settings.json` files. Enable only the parts you need. Existing features default to enabled; `step-trace` diagnostics default to disabled. [Configure plugin features](CONFIGURATION.md) lists every switch, model shortcut, feedback interval, and reload behavior.

The groups share model/effort state, feedback observation and ticking, and inspection dialog/context reads. They keep separate feature modules and data sources. The pinned xyaman Vim implementation remains unchanged.

```sh
python3 -B yuke/tests/check-plugin-groups.py
python3 -B yuke/tests/check-feedback.py
```

## Build label

The bottom bar and `/status` Build row omit the build timestamp and shorten the
source revision to eight characters. `yuke --version` and RPC keep the full
embedded build identity. The UI reads the running engine, not another executable
on `PATH`.

```sh
node yuke/tests/check-version-label.mjs
python3 -B yuke/tests/check-build-status.py --binary "$HOME/.local/bin/yuke"
```

## Herdr agent reporting

The Herdr plugin starts reporting after `ui.started`, when the interactive frontend is ready. It reports again after native `/reload` and releases the pane on quit. `yuke check` and nested agents do not report over the parent pane.

Pending clarification questions also report `blocked`, without opening the inbox. Herdr sends its normal needs-attention notification when the pane becomes blocked. A question batch causes one state transition. Repeated inbox polls do not send another report. Answering or dismissing the questions clears this block. Questions in other sessions do not block this pane. Herdr's notification settings still control delivery.

The question plugin provides the `yuke-clarify` capability with `pending(sessionId)` and the `yuke-clarify:changed` event. The capability includes pending questions and uncertain answer deliveries. The Herdr plugin reads it at startup, on session changes, and when the inbox state changes. It keeps Herdr socket operations out of the question plugin.

After installing a plugin edit, wait for the active run to finish, save any typed draft, and run `/reload` in each Yuke session. Herdr does not need a server restart.

Run the regression against private Herdr panes and a detached Herdr client:

```sh
python3 -B yuke/tests/check-herdr.py
```

The check uses temporary homes and stores, real private Herdr panes, and a detached Herdr client. It checks the visible question notification with sound disabled. It does not copy provider credentials, make model calls, or touch live sessions.

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

[Pre-manifest tests and guides](tests/pre-manifest/README.md) remain as reference material for later ports. They are not the current verification suite. The [loop plugin](LOOP.md) now uses manifests and native terminal-turn outcomes. The [Peek observer](.config/yuke/plugins/peek/README.md) makes separate tool-free model requests. Both entries are in the source configuration. An installed profile can omit those two entries. Consolidating the four groups does not enable Loop or Peek in a profile that did not already list them.

The current candidate passes the full imported Vim invariant, search, and transcript checks. Editing parity matches real Vim in 581 cases. Transcript parity matches 48 cases. The 22-entry source profile passes types, startup, input, reload, disposal, and headless checks in both motion modes. See [Dashboard reuse](DASHBOARD.md) and [Work activity](WORK.md) for their checks.

Broader dialog and service checks and performance investigations remain open. The earlier allocation differences remain unexplained. The startup and input guards do not prove every external integration or paid-provider route. These candidate checks do not install or activate the source profile.
