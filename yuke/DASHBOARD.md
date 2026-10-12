# Empty-chat dashboard

The `yuke-dashboard` manifest replaces the title and hint of each empty chat pane. It shows the workspace, selected model, and available startup actions. Saved transcripts retain their normal display.

## Reuse in a profile

Keep the dashboard folder under the profile's `plugins/` directory. Add `./plugins/yuke-dashboard` to `config.json`. The manifest requires `tui` and `composer-vim`. Include the pinned `vim-mode` provider to supply `composer-vim`. Without those services, the plugin does nothing.

The Vim source record has no confirmed redistribution license. This profile is for personal use. Confirm its reuse terms before redistribution.

The dashboard calls existing commands. It does not implement sessions, search, project work, or model selection. It checks command availability after all plugins load. Optional commands have no row or letter when their plugin is absent.

| Letter | Command | Action |
| --- | --- | --- |
| `r` | `ui:sessions` | Resume a session |
| `s` | `search:open` | Search chats and files |
| `w` | `project-work:work` | Open project tasks and checkpoints |
| `m` | `model:pick` | Choose a model |
| `c` | `ui:palette` | Open commands |
| `q` | `quit` | Quit Yuke |

Click an action row to run the same command. Press `i` to type a prompt. Press Escape to return to normal mode.

## Input and lifetime

A new empty pane starts in normal mode. Returning to the same pane preserves its selected mode. Dashboard letters run only in the active empty normal-mode composer. Open dialogs and pending window chords retain their keys. Insert mode types the letters. A nonempty draft retains Vim's normal-mode commands.

The view clips and positions text when its bounds or content change. Drawing reads cached rows. Ordinary saved-chat input has no dashboard key interceptor. The plugin owns its advice, listeners, and pane replacements. Unloading restores the original title and hint only if the dashboard still owns them. It does not overwrite a later replacement from another plugin.

Native `/reload` disposes the old instance before loading the new instance. Profile changes remain separate from the installed copy. Copy only an intentional plugin edit to the active profile. Do not overwrite credentials or private settings.

## Verification

Run the source profile guard with a verified candidate binary and its generated declarations:

```sh
python3 -B yuke/tests/check-profile.py \
  --binary /absolute/path/to/yuke \
  --types-dir /absolute/path/to/types
python3 -B yuke/tests/check-work-activity.py \
  --binary /absolute/path/to/yuke
```

The first check covers startup input, modal priority, and two native reload generations in logical and display-row modes. The second checks the actual startup Search and Work actions and dispatches `w` through the root key handler. Both use private profiles and detached terminals. They make no model call and send no desktop input.

These checks do not prove every optional action or external integration. Performance results belong to the current benchmark report. Historical factory-plugin reports do not verify this manifest version.
