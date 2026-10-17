# Configure Yuke plugin features

The profile groups related features into `models`, `controls`, `run-feedback`, and `insights`. Each group reads its own `settings.json`. Other plugins remain independent entries in `config.json`.

## Continue a conversation in another checkout

The `session-fork` plugin exposes `fork_session` in every frontend. It requires a Yuke build that implements workspace-aware `session.fork`. A skill alone cannot enable this native operation.

Ask the agent to create the requested jj workspace, call `fork_session` with that directory, and open a Herdr pane there. The tool returns the new session ID and `yuke resume <id>` command. Launch that ID in the pane. A panel-launch retry uses the same ID instead of making another fork.

The new session keeps committed history, compaction, attachment references, and model settings. It loads instructions and skills from the destination. It does not copy the live assistant draft, that draft's tool results, queued input, children, running jobs, pending dialogs, or unsent text. Leave the source open unless the user asks to close it. Name already completed setup actions in the continuation prompt so the new agent does not repeat them.

The source profile lists this plugin. Source preparation does not install its required native build or change an active chat's tool catalog. Install a combined build that preserves other current native changes before copying the plugin into the normal profile. Save unsent text and restart Yuke after a native update. Do not use only `/reload` for a binary change.

## Change this conversation's workspace

The `workspace` profile plugin owns `/cd <path>` and `/pwd`. Its `"./plugins/workspace"` entry is enabled in `config.json`. It needs the public `workspace` API in the native build. `/pwd` shows the current workspace without changing the conversation or its draft. `/cd` without an argument also shows the current workspace.

The enabled `path-completion` plugin lists only directories after `/cd `. It supports a bare name, `./`, `../`, `~/`, and `/`. Tab or Enter completes the selected directory without submitting the command. Completion adds quotes when a name contains spaces. Matching outer quotes delimit the path. They do not execute shell expressions.

The command forks committed history into the destination and leaves the source unchanged. It reloads destination instructions, skills, tool activation, and MCP context. Default file access and new chats use the destination. It requires one pane and refuses active work, queued input, running jobs, or an unsaved draft.

After a native update, save the draft and restart Yuke. Resume the saved conversation before using `/cd`. `/reload` alone cannot add a native command to an older binary.

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
| `startupModel` | `""` | Model selector used as the default for new TUI chats after startup or reload. Set together with `startupEffort`. |
| `startupEffort` | `""` | Reasoning effort for `startupModel`. Existing saved chats keep their settings. |

For ordinary work on Sol at medium effort, set both startup options:

```json
{
  "startupModel": "openai-codex/gpt-6.1-sol",
  "startupEffort": "medium"
}
```

The model and effort must exist in the loaded catalog. Otherwise, the plugin warns and retains the existing default. An explicit model or effort choice takes precedence, including a choice made while the catalog loads. Startup defaults do not change headless runs or child-agent roles.

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
| `phaseTimers` | `true` | A display-only live action at the end of the response. Intermediate completed records stay visible. The final summary disappears when the run ends. Requires `chat`. Queued inputs keep their own prompt rows. |
| `stepTimers` | `true` | Live reasoning duration and tracking of tool and reasoning clocks. Requires the `chat` capability. |
| `speedRefreshMs` | `250` | Refresh interval for live token speed. |
| `timerRefreshMs` | `100` | Refresh interval for phase and transcript clocks. |

Selected features share one engine-drain listener and one frame clock. The clock runs only while selected feedback needs updates. It preserves each feature's interval. Saved provider durations take precedence over locally observed durations. Observed phase blocks do not enter engine messages or model context. Reload removes those display-only observations.

Disabling every feature registers no feedback listener or clock. It does not hide Yuke's bundled run indicator or completed-tool durations.

### Activity states

The engine reports one coarse state per session. These states describe observed engine work, not the model's private computations.

| Engine state | Display | Meaning |
|---|---|---|
| `idle` | No active phase | This session has no active run. A child session can still work. |
| `building` | preparing request | The engine prepares the request before it opens a provider round. This can include request hooks and context preparation. |
| `waiting` | waiting for model response | The provider round exists, but the engine has not accepted a successful response header. This includes connection and server delay. |
| `streaming` | reading model response | The response stream is open, and no running tool or latest reasoning part takes priority. Text, tool arguments, and gaps between output blocks can all use this state. |
| `reasoning` | reading reasoning | The latest native draft part is an unfinished reasoning part, and no tool runs. A provider can hide its reasoning text. This state does not prove that the model still computes reasoning. |
| `running_tool` | running TOOL | A tool executes. The engine chooses the first running tool when several tools run. Tool headings keep their own durations. |
| `retrying` | waiting to retry model, attempt N | The engine waits before another request attempt after a provider failure. The bundled indicator also shows the retry countdown and error code. |
| `compacting` | compacting context | The engine summarizes older context. Compaction can start automatically or from a manual request. |

The bundled indicator calls `streaming` "responding". The timing heading calls it "reading model response" to avoid a promise of visible answer text. The engine enters this state after a successful HTTP response header, sometimes before the first output arrives. Yuke displays answer text as chunks arrive. Between chunks, the open stream waits for the provider's next bytes.

A timing block uses the same heading styles and fold behavior as a thought entry. Its clock mark identifies UI metadata. The live action follows the last response part, including new thoughts and tool output. It shows verbs such as `◷ waiting for model response · 8s`, `◷ reading model response · 2m8s`, and `◷ running exec · 1h2m8s`. The live clock measures the current action. After an intermediate response ends, the same entry shows `◷ waited for model response · 2m8s`. The final timing summary disappears when the run ends. Thought and tool durations remain visible. Its completed total excludes observed tool execution. A click or Ctrl+O expands the phase breakdown. Completed thoughts and actions stay in their original order.

A thought is a reasoning part of an assistant message. A timing block is local display data, not an assistant message in engine history.

Phase durations use the UI's observation times. Coalesced activity events can omit short intermediate states. A phase duration is not provider compute time. Reasoning and tool headings use stored durations when the engine supplies them.

A completed hidden thought whose engine duration rounds to zero can show `thought for ~8s`. This is an estimate from the observed wait before its completed payload arrived. The first hidden block uses the observed request start. A later hidden block uses the previous observed hidden-block arrival. Network delays, server queues, retries, and other model output can enter this interval. It is not a measurement of private model computation. Expand the thought heading for that explanation.

Coalesced hidden blocks can arrive together and have no separate estimate. Old blocks from before the observer started also have no estimate. They show `thought for an unknown time`. The plugin does not infer a duration from the whole turn or overwrite stored durations and encrypted replay data.

Phase, thought, and built-in tool clocks use short h/m/s labels. Examples are `8s`, `2m8s`, and `1h2m8s`. A subsecond duration reads `<1s`. The built-in tool format and corrected native reasoning state require the updated binary, not only a profile reload.

Intermediate blocks stay beside their responses until the session closes or plugins reload. They do not use the engine store. A restart or reload cannot restore past observations. An ended phase means that its state changed, not that the request succeeded.

## Insights

File `plugins/insights/settings.json`.

| Option | Default | Behavior |
|---|---|---|
| `status` | `true` | `/status` with model, session, build, and provider limits. Codex and OpenRouter use their quota endpoints. xAI shows the current usage-pool share left when the login reports one. |
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
