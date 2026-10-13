# Configure Yuke plugin features

The profile groups related features into `models`, `controls`, `run-feedback`, and `insights`. Each group reads its own `settings.json`. Other plugins remain independent entries in `config.json`.

## Select features

Create `~/.config/yuke/plugins/<group>/settings.json`. Set only the options you want to change. A missing file or omitted option uses the defaults below.

For example, keep token speed without phase rows or reasoning clocks:

```json
{
  "tokenSpeed": true,
  "phaseTimers": false,
  "stepTimers": false,
  "speedRefreshMs": 500
}
```

Save this example as `plugins/run-feedback/settings.json` under your profile.

Wait for active runs and tool calls to finish. Save any typed draft before running `/reload`. Reload reads settings again and releases the old listeners, commands, views, and clocks. It can discard the draft. A native binary update requires a restart instead.

Settings must be a JSON object. Unknown names and incorrect types report a plugin-load error. Use `false`, not the string `"false"`. Interval values must be integer milliseconds from 16 to 60000. Fix an invalid file before reloading again. Other plugins can still load when one group fails.

## Models

File `plugins/models/settings.json`.

| Option | Default | Behavior |
|---|---|---|
| `picker` | `true` | Enhanced `/model` picker with numbered choices. |
| `effortPicker` | `true` | Standalone `/effort` command. The model picker still asks for effort when a model supports it. |
| `aliases` | `true` | Model aliases, their shortcuts, favorites, and editing controls in the enhanced picker. |
| `effortStatus` | `true` | Reasoning effort beside the model in the status bar. |
| `modelKey` | `"ctrl+x m"` | Shortcut for the enhanced picker. An empty string omits this group's binding. |
| `effortKey` | `"ctrl+x e"` | Shortcut for `/effort`. An empty string omits this group's binding. |

For effort controls and status without the enhanced model picker or aliases:

```json
{
  "picker": false,
  "aliases": false
}
```

Disabling `picker` leaves Yuke's bundled `/model` behavior intact. Aliases can work independently of the enhanced picker. Disabling `aliases` leaves the existing `model-aliases.json` untouched and does not read it.

Aliases remain in the profile-level `model-aliases.json`. Each preset can select a model or latest model family, choose an effort, and bind a key. Existing files keep their schema and revision checks. With aliases enabled, the enhanced picker uses Ctrl+A to set an alias, Ctrl+R to remove it, and Ctrl+E to change its effort. Those editing bindings disappear when aliases are disabled.

Example preset file:

```json
{
  "version": 1,
  "revision": 0,
  "presets": [
    {
      "alias": "fast",
      "model": "provider/model",
      "effort": "low",
      "key": "ctrl+x f"
    }
  ]
}
```

Replace `provider/model` and `low` with values supported by your catalog. Preserve the revision when editing an existing file. The model picker updates it when saving an edit.

## Controls

File `plugins/controls/settings.json`.

| Option | Default | Behavior |
|---|---|---|
| `clearAlias` | `true` | `/clear` starts a new empty chat. |
| `exitAliases` | `true` | `/exit` and `/close` use graceful quit. |
| `interrupt` | `true` | Personal Ctrl+C behavior, including clearing a draft, interruption, and double-press exit. Requires `vim-mode`. |
| `navigation` | `true` | Ctrl+H/J/K/L pane navigation and the normal-mode slash shortcut. Requires `vim-mode`. |
| `panelCommand` | `true` | `/panel split`, `vsplit`, `close`, and `only`. Works without Vim. |

For only the pane command:

```json
{
  "clearAlias": false,
  "exitAliases": false,
  "interrupt": false,
  "navigation": false
}
```

Disabling personal key handling does not disable Yuke's bundled keys. Prompt-history and clarification plugins keep their own shortcuts. The default combination preserves clarification priority for Ctrl+H and prompt-history priority where applicable.

## Run feedback

File `plugins/run-feedback/settings.json`.

| Option | Default | Behavior |
|---|---|---|
| `tokenSpeed` | `true` | Live estimated output speed and provider-reported speed after commit. |
| `phaseTimers` | `true` | Display-only request and model phase blocks in the transcript. Requires `chat`. Queued inputs keep their own prompt rows. |
| `stepTimers` | `true` | Live reasoning duration and tracking of tool and reasoning clocks. Requires the `chat` capability. |
| `speedRefreshMs` | `250` | Refresh interval for live token speed. |
| `timerRefreshMs` | `100` | Refresh interval for phase and transcript clocks. |

Selected features share one engine-drain listener and one frame clock. The clock runs only while selected feedback needs updates. It preserves each feature's interval. Saved provider durations take precedence over locally observed durations. Observed phase blocks do not enter engine messages or model context. Reload removes those display-only observations.

Disabling every feature registers no feedback listener or clock. It does not hide Yuke's bundled run indicator or completed-tool durations.

## Insights

File `plugins/insights/settings.json`.

| Option | Default | Behavior |
|---|---|---|
| `status` | `true` | `/status` with model, session, build, and provider limits. |
| `context` | `true` | Enhanced `/context` with budget, instructions, skills, and tools. |
| `usage` | `true` | `/usage` with historical usage, costs, tools, skills, and chats. |

For only the account and session card:

```json
{
  "context": false,
  "usage": false
}
```

Disabling `context` restores Yuke's bundled context command. The other disabled views do not register their commands or start readers. Views read on open or refresh. Context inspection does not fetch account quotas or scan historical usage. Closing a view cancels its owned readers and preserves the chat draft.

## Diagnostic tracing

`step-trace` is separate from normal feedback and is off by default. To enable its diagnostic logs, create `plugins/step-trace/settings.json`:

```json
{
  "enabled": true
}
```

It logs tool transitions, model phases, cancellation timing, and unsettled operations. It does not log tool argument or result contents. Set `enabled` to `false` and reload to remove its hooks and monitor. Do not infer tool completion from a diagnostic heartbeat.

## Select whole plugins

Remove a folder from `config.json`'s `plugins` list to stop loading that custom plugin. Keep only the groups and integrations you need. The `disable` list is for bundled Yuke plugins, not these custom feature switches.

`vim-mode` is the pinned copy of xyaman's implementation described in [Vim source](.config/yuke/plugins/vim-mode/SOURCE.md). This consolidation does not modify it. Its own `settings.json` still controls logical or display-row vertical movement. Features that require `composer-vim` skip their Vim-dependent behavior when that capability is absent.

## Verify changes safely

Run from the dotfiles root:

```sh
python3 -B yuke/tests/check-plugin-groups.py
python3 -B yuke/tests/check-feedback.py
python3 -B yuke/tests/check-profile.py \
  --binary "$HOME/.local/bin/yuke" \
  --types-dir "$HOME/.local/lib/yuke/types"
```

The drivers use private profiles, homes, stores, and detached terminals. The feedback driver uses a local provider fixture. They do not use normal provider credentials, send paid model requests, reload live sessions, or forward clipboard output. The full profile guard also checks that a native reload applies disabled feature settings.
