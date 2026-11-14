# Configure Yuke plugin features

The profile is `~/.config/yuke-rust`, stowed from `~/dotfiles/yuke-rust/.config/yuke-rust`. Its `config.json` lists every plugin. Plugin data is in `~/.local/share/yuke-rust/plugins/<name>`.

## Plugin options

Only `models`, `run-feedback`, and `step-trace` take options. Give a plugin options by replacing its string entry with an object:

```json
{
  "path": "./plugins/run-feedback",
  "options": {
    "phaseTimers": false,
    "stepTimers": false,
    "speedRefreshMs": 500
  }
}
```

This example keeps token speed without phase cards or reasoning clocks. Set only the options you want to change. An omitted option uses the default below. Use `false`, not the string `"false"`.

Wait for active runs to finish and save any typed draft. Then run `/reload` while idle. Reload reads options again and disposes the old commands, keys, listeners, and timers. A native binary update needs a restart instead.

## Models

Entry `"./plugins/models"`. The profile sets `startupModel` and `startupEffort`.

| Option | Default | Behavior |
|---|---|---|
| `picker` | `true` | Plugin model picker, `/model`, and its key. |
| `effortPicker` | `true` | `/effort` and its key. |
| `aliases` | `true` | One command per alias, alias keys, and `/model-aliases`. |
| `modelKey` | `"ctrl+x m"` | Key for `/model`. |
| `effortKey` | `"ctrl+x e"` | Key for `/effort`. |
| `startupModel` | `""` | `provider/model` chosen for the chat when the first composer appears. |
| `startupEffort` | `""` | Reasoning effort for `startupModel`. |

Set `startupModel` and `startupEffort` together. Setting only one fails the plugin load. The model and effort must exist in the loaded catalog. Otherwise, the plugin warns and keeps the saved default.

`/model` without an argument opens a model list and then an effort list. `/model <alias>` uses that alias and its effort. `/model provider/model` selects that exact model. `/effort` lists the current model's efforts. `/effort <level>` selects one directly.

With `picker` set to `false`, the plugin registers no model picker, `/model` command, or model key.

Reasoning effort appears in the native model status. The plugin has no status option.

### Aliases

Aliases are in `~/.local/share/yuke-rust/plugins/models/model-aliases.json`. Without that file, the plugin uses two built-in aliases, `sh` and `lm`. An invalid file fails the plugin load.

Each alias names a model or the latest model of a family, and can set an effort and a key:

```json
{
  "version": 1,
  "revision": 0,
  "presets": [
    {
      "alias": "sh",
      "latest": { "provider": "openai-codex", "family": "sol" },
      "effort": "high",
      "key": "ctrl+x s"
    },
    {
      "alias": "fast",
      "model": "provider/model",
      "effort": "low"
    }
  ]
}
```

Set either `model` or `latest`, not both. `latest.family` is `sol` or `luna`. It selects the newest `gpt-<version>-<family>` model of that provider. Alias names use lowercase letters, digits, and `-`, and start with a letter. A file holds at most 64 aliases.

Each alias adds a `/<alias>` command and binds its key. `/model-aliases` opens the file as JSON. Ctrl+S validates and saves it. The save checks the revision, so a concurrent edit is not lost. Run `/reload` to apply command and key changes.

With `aliases` set to `false`, the plugin adds no alias commands, keys, or editor. It still reads the alias file at load.

## Controls

Entry `"./plugins/controls"`. It has no options and requires the `vim` plugin.

- `/exit` and `/close` quit Yuke.
- `/clear` starts an empty chat.
- `/panel split`, `vsplit`, `close`, and `only` split the pane down, split it right, close it, or close the other panes.
- Ctrl+H, Ctrl+K, and Ctrl+L focus the pane to the left, above, or to the right. Ctrl+J focuses the pane below outside Insert mode.

Ctrl+C in the composer works in layers:

1. A nonempty draft is cleared, and the composer returns to Normal mode.
2. An empty draft in Insert mode returns to Normal mode.
3. An empty draft in Normal mode interrupts the chat and shows `press Ctrl+C again to exit`.
4. A second Ctrl+C then quits.

Any other key, a click, a paste, or a focus change cancels the pending exit.

## Run feedback

Entry `"./plugins/run-feedback"`.

| Option | Default | Behavior |
|---|---|---|
| `tokenSpeed` | `true` | Output speed in the status bar. |
| `phaseTimers` | `true` | A timing card after each response. |
| `stepTimers` | `true` | A live clock on reasoning headings. |
| `speedRefreshMs` | `250` | Refresh interval for live feedback. |
| `timerRefreshMs` | `100` | Refresh interval for live feedback. |

Interval values are integer milliseconds from 16 to 60000. One timer runs at the shorter of the two intervals, and only while a response or its tools run.

Token speed reads `~N tok/s` while it estimates from streamed characters. After the response completes, it uses the provider's output token count and drops the `~`. It reads `— tok/s` when nothing is measured.

The timing card lists observed phases in order: `waiting`, `thinking`, `tool input`, `responding`, and `tools`. For example, `waiting 2s · responding 5s · tools 1m3s`. Durations use short h/m/s labels. A subsecond duration reads `<1s`.

These are UI observation times, not provider compute time. The cards do not enter engine history or model context. They stay until the plugin reloads or Yuke exits. A restart or reload does not restore them.

With all three features set to `false`, the plugin registers nothing.

## Insights

Entry `"./plugins/insights"`. It has no options. `/status` and `/context` need a saved session.

`/status` shows the build, model, workspace, session state, queued inputs, last reported input and output tokens, registered tools, and prompt section sizes. It also shows account allowances for `openai-codex`, `xai-grok`, and `openrouter`.

`/context` has four views: budget, saved blocks, prompt preview, and registered tools. Tab cycles them. Token counts are estimates.

`/usage` shows usage by day, model, tool, skill, and chat. Alt+1 to Alt+6 or Tab select its tabs. Alt+W switches between this workspace and all workspaces. `g` cycles the period.

Ctrl+R refreshes each view. `j`, `k`, and the page keys scroll.

## Diagnostic tracing

`step-trace` is off by default. To enable it, set its entry to:

```json
{ "path": "./plugins/step-trace", "options": { "enabled": true } }
```

It logs `STEP_TRACE` lines for tool starts and finishes, event-loop gaps, and tools still running every 30 seconds. It does not log tool arguments or output. Set `enabled` to `false` and reload to remove it.

## Continue a conversation in another checkout

The `session-fork` plugin adds the `fork_session` tool. Ask the agent to call it only when you want a fork.

`fork_session` copies history through the newest completed turn, or through `through_event`, into an independent session. `workspace_path` is an existing absolute folder. Omit it to keep the source workspace. The destination supplies its own instructions, skills, and MCP configuration.

Queued inputs, active drafts, children, and jobs stay with the source. The tool starts no model turn and opens no pane. It returns the new session ID and a `yuke --session <id>` command. A cancelled call can still create a fork, so inspect sessions before retrying.

## Change this conversation's workspace

The `workspace` plugin adds `/pwd` and `/cd <path>`. `/pwd` and `/cd` without an argument show the current workspace.

`/cd` resolves the path from the current workspace. It accepts `~/` and strips one pair of matching outer quotes. The destination must be a directory.

For a saved conversation, `/cd` forks its history into the destination and shows the fork. The destination's instructions apply. The source session stays unchanged. A new chat without a saved conversation moves to the destination without creating one.

`/cd` requires one pane. It refuses while a turn, queued input, or background job is active.

### Path completion

The `path-completion` plugin completes paths in the composer in Insert mode. After `/cd `, it lists only directories. A bare name searches the current workspace. `./`, `../`, `~/`, and `/` also work.

Up, Down, Ctrl+P, and Ctrl+N move the selection. Tab or Enter completes it without submitting. Esc dismisses the list. A completed directory opens its contents. Completion adds quotes when a name contains spaces or quotes.

## Select whole plugins

Remove an entry from the `plugins` list in `config.json` to stop loading that plugin. Then run `/reload` while idle.

`controls` and `path-completion` require the `vim` plugin. Without it, they load but do nothing.

## Checks

Run all profile checks:

```sh
python3 ~/dotfiles/yuke-rust/scripts/verify.py --source ~/workspace/yuke --binary ~/.local/lib/yuke-rust/bin/yuke
```

`tests/terminal.py` drives a private profile in a detached terminal. It sets the startup model, completes paths and a quoted `/cd` directory, runs `/panel`, `/clear`, `/reload`, `/context`, and `/usage`, and switches workspace with `/cd`. It asserts zero model requests.

`tests/tools.test.ts` checks that a destination fork uses the target instructions and leaves the source prompt unchanged. `tests/test_model_alias_store.py` checks alias revision conflicts and that bad files and symlinks are not overwritten.

No test covers `run-feedback` or `step-trace` output.
