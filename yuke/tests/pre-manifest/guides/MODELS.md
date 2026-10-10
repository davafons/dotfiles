# Model and effort controls

The `model-manager` profile plugin adds numbered choices, editable model aliases, and shortcuts. It does not change the engine or send a chat message when you select or edit a model.

Run `/reload` to load it with this profile's reload loader. A restart also loads it.

## Model list

`/model` shows one row per catalog model. Rows show model names, not alias commands.

Models with aliases are favorites. They have a star and an alias badge, for example:

```text
1) ★ GPT-6.1 Sol     alias sh · high · openai-codex
2) ★ GPT-6 Luna      alias lm · medium · openai-codex
3)   another model   provider
```

Favorites appear first in alias order. Remaining models group by provider and sort by descending name. Several aliases for the same model still produce one model row. Unresolved aliases do not create placeholder rows. Their commands report that the model is unavailable.

Type to filter by model name, provider, or alias. Press `1` through `9` to select the corresponding numbered row. After a filter, the numbers refer to the filtered list. Number keys select instead of entering query text. Use `/model provider/model` for a selector that needs digits.

Use arrows or Ctrl+P/Ctrl+N to reach later rows. Press Enter to accept. The picker shows at most nine rows at once. Number keys refer to rows 1–9 in the filtered list, not to a new page after scrolling.

Selecting a model opens its effort picker. It suggests the alias's saved effort, a supported current effort, or the model default. The model changes only after effort confirmation. Esc keeps the previous model and effort. A model without effort levels applies directly.

## Edit aliases in the list

Select a model with arrows or filter text. These keys edit the selected row without changing the current session model or its draft:

| Key | Action |
|---|---|
| Ctrl+A | Set or rename its alias. Blank removes an existing alias. |
| Ctrl+E | Set the alias's default effort in a numbered picker. |
| Ctrl+R | Remove its alias after confirmation. The model stays in the list. |
| Esc | Cancel the dialog or close the list. |

An alias makes the model a favorite. Removing its last alias removes the star and returns the model to normal catalog order. Changes register or remove the slash command immediately. Rename keeps an existing alias's shortcut and latest-family rule. Removal also removes its shortcut. If a model has several aliases, the editor first asks which one to change.

New aliases pin the selected model's exact selector. They use a supported current effort, or the model default. Ctrl+E changes that default. Editing an alias's default does not change the current session effort. Use `/effort` for that.

An alias starts with a lowercase letter. It can contain lowercase letters, digits, and hyphens, up to 32 characters. An optional leading `/` in the editor is allowed. Duplicate aliases and names that belong to another command cannot be saved.

The picker returns to the same filter and model after an edit. Cancelling an editor makes no change.

## Commands and shortcuts

| Command | Action |
|---|---|
| `/model` | Choose a model, then its effort; edit aliases in the same list. |
| `/model 2` | Apply row 2 from the unfiltered list immediately. |
| `/model provider/model` | Apply an exact model selector immediately. |
| `/model alias` | Apply that alias's model and effort immediately. |
| `/alias` | Apply that alias directly, for example `/sh`. |
| `/effort` | Open numbered effort choices for the current model. |
| `/effort medium` | Set medium effort without changing the model. |
| `/effort off` | Disable reasoning when the model supports it. |
| `/effort 2` | Select the second supported effort level. |

The profile enables these chords. Press Ctrl+X, release it, then press the letter:

- Ctrl+X, M opens the model list.
- Ctrl+X, E opens effort choices.
- Ctrl+X, S applies the initial Sol alias.
- Ctrl+X, L applies the initial Luna alias.

Shortcuts work in a chat pane outside modal dialogs. They keep the draft. The dashboard's normal-mode M action opens the same model list.

Direct aliases and argument commands do not ask for effort. An alias without a saved effort retains a supported session effort, else uses the model default. For a fresh draft, the plugin can retain only an effort selected since it loaded. It uses the model default when that draft effort is unknown.

Selections use Yuke's `Session.setModel` API. An existing session changes only after the engine accepts the patch. A running turn keeps its original settings. The next turn uses the new choice. Yuke also uses the choice as the default for a new chat.

Slash aliases are commands on their own line. They do not strip prefixes from a prompt. `#sh` and Markdown headings stay ordinary text.

## Saved settings and initial defaults

Edits save to `~/.config/yuke/model-aliases.json`, or the corresponding XDG/YUKE_APPNAME profile directory. Writes use an atomic replacement and mode `0600`. A revision check prevents one Yuke process from overwriting another process's newer edit. If a save conflicts, reopen `/model` and try again.

Invalid saved settings report an error. The editor does not overwrite a malformed file or a symlink. The helper uses Python 3. It runs only on edits; model selection does not start it.

Before the first saved edit, `profile.js` supplies these defaults:

```js
ctx.use(modelManager({
  modelKey: "ctrl+x m",
  effortKey: "ctrl+x e",
  presets: [
    { alias: "sh", latest: { provider: "openai-codex", family: "sol" }, effort: "high", key: "ctrl+x s" },
    { alias: "lm", latest: { provider: "openai-codex", family: "luna" }, effort: "medium", key: "ctrl+x l" },
  ],
}));
```

Once the saved file exists, it replaces the initial defaults. Removed defaults stay removed after reload and restart. Use the UI to change saved aliases. The editor does not modify `profile.js` or `providers.json`.

The initial Sol and Luna aliases follow the newest base version within `openai-codex`. They compare numeric version components, so 6.10 is newer than 6.9. They match IDs such as `gpt-6.1-sol`, not Pro, dated, or preview variants. They do not cross providers or fall back to an older model when the newest model refuses the effort or lacks credentials. Renaming these aliases preserves this behavior.

Profile defaults can use `model: "provider/model-id"` instead of `latest`. Set exactly one of `model` and `latest`. A preset's optional `key` binds a direct shortcut. Omit `modelKey` or `effortKey` to disable those menu shortcuts.

## Verify

```sh
python3 ~/.config/yuke/tests/check-model-alias-store.py
python3 ~/.config/yuke/tests/check-model-manager.py
tsc -p ~/.config/yuke/jsconfig.json
yuke check
```

The TUI test uses a detached tmux server, an isolated profile and session store, and a loopback model provider. It checks model rows and favorite markers, numbered model-to-effort selection, cancellation, aliases and shortcuts, alias editing, duplicate rejection, default-effort edits, persistence across plugin reload and process restart, removal of commands, saved session settings, next-turn requests, and latest-version selection. It saves labeled captures. It does not use desktop input, the clipboard, or external model services.

The store test checks concurrent revision conflicts, atomic saved results, empty settings, file permissions, and preservation of malformed files and symlinks.
