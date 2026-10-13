# Empty-chat dashboard

The `yuke-dashboard` manifest replaces the title and hint of each empty chat pane. It shows the workspace, selected model, and available startup actions. Saved transcripts retain their normal display.

## Reuse in a profile

The dashboard loads from `lostcoords/yuke-plugins` at the commit in `config.json`. Do not keep a second copy under `plugins/`. Personal rows are a local plugin, `dashboard-config`, which calls `setup` on the `yuke-dashboard` capability. Vim can be absent. Without a `setup` call, letter keys stay off.

| Letter | Command | Action |
| --- | --- | --- |
| `l` | `auth:login` | Sign in |
| `r` | `ui:sessions` | Resume a session |
| `s` | `search:open` | Search chats and files |
| `w` | `project-work:work` | Open project tasks and checkpoints |
| `m` | `model:pick` | Choose a model |
| `c` | `ui:palette` | Open commands |
| `q` | `quit` | Quit Yuke |

Click an action row to run the same command. An assigned letter runs that row only while the draft is empty. Any other character starts the prompt.

## Input and lifetime

Assigned letters run on an empty draft in the active chat, including while Vim is in normal mode. A nonempty draft types those letters.

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
