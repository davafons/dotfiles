# Startup dashboard

The `yuke-dashboard` profile plugin replaces the empty-chat hint with a centered YUKE logo, the launch workspace, the selected model, and an action menu. It uses the current theme. A small pane shows a compact header and fewer details.

The dashboard appears when Yuke opens a draft and after `/new` or Ctrl+N. This profile also provides `/clear` as an alias. A new empty draft starts in normal mode. Switching back to an existing pane preserves its selected mode. A saved conversation keeps its normal transcript. The dashboard does not open a dialog or send a model request at startup.

## Actions

These letters run actions only when the composer has focus, the draft has no text or image attachment, and Composer Vim is in normal mode.

| Action | Key | Command |
|---|---|---|
| Resume a session | r | `/sessions` |
| Search chats and files | s | `/search` |
| Project tasks and checkpoints | w | `/work` |
| Choose a model | m | `/model` |
| Commands | c | Command palette |
| Quit Yuke | q | Graceful quit |

Press `i` to enter insert mode and type a prompt. Press Esc to return to normal mode. In insert mode, action letters type text. A nonempty draft keeps its normal Vim editing keys. Open dialogs keep their own keys. The dashboard registers no Alt shortcuts. Existing Ctrl+F, Ctrl+P, Ctrl+N, and Ctrl+Q bindings remain available.

Click an action to run it. The menu uses the registered command, so the session browser keeps its ownership checks and quit keeps its guards.

Search and work rows appear only when their plugins are registered before the dashboard. The dashboard has no dependency on either plugin. Register optional action plugins first.

## Profile

The dashboard requires the `composer-vim` capability. Your `insert-status-left` plugin already loads `vim-improved`, which enables Composer Vim and transcript Vim. The dashboard reuses that provider. It does not install a second Vim plugin.

For another profile, copy `plugins/yuke-dashboard.js` into its `plugins/` directory. A minimal `index.js` uses the bundled Composer Vim provider:

```js
import { plugins } from "yuke";
import { composerVim } from "yuke:plugins";
import { yukeDashboard } from "./plugins/yuke-dashboard.js";

plugins.use(composerVim);
plugins.use(yukeDashboard);
```

Register any optional action providers before the dashboard. Do not add `composerVim` when another plugin already provides it. Without `composer-vim`, the dashboard does not activate.

Your reloadable `profile.js` registers the dashboard after the action providers:

```js
import { yukeDashboard } from "./plugins/yuke-dashboard.js";

ctx.use(yukeDashboard);
```

Use `/reload` with this profile's reload loader, or restart Yuke. A plain profile without that loader requires a restart.

Edit `ACTIONS` in `.config/yuke/plugins/yuke-dashboard.js` to change the menu labels, letters, or command targets. Edit `LOGO` to change the header. The default highlight groups are `DashboardLogo`, `DashboardAction`, `DashboardKey`, and `DashboardContext`.

The plugin owns each replacement hint. Unloading restores each original title or hint only if the dashboard still owns that field. It preserves later replacements from other plugins. It does not replace the composer, session, or transcript. It caches drawing rows until the pane size, workspace, or model changes. It does not wrap or allocate rows during draw. It leaves `ChatView.layout` and `ChatView.draw` unchanged.

The dashboard intercepts its letters before Vim parses a mark or operator. This input advice exists only while an empty draft composer has focus in normal mode. The plugin removes it on insert mode, a text or image attachment, transcript focus, a session change, or unload. Pending keymap sequences keep their next key. The plugin follows the new-chat command as well as session events, because a new draft can have the same null session ID as the old draft.

## Earlier drawing measurement

A scratch copy of the Yuke benchmark loaded the original dashboard version in its chat harness. Five alternating ReleaseFast runs per side used 3,000 iterations and five repeats per run. The lowest-quartile frame time changed by -0.51%. Stream time changed by +0.54%. Both differences are below the benchmark's stated timing noise; they do not establish a speed change. Callgrind was unavailable on this machine.

That metrics build found identical active-chat frame allocation counts and drawing counters with and without the plugin. Allocation slopes stayed at zero in both the 1,500–3,000 and 4,500–6,000 frame windows. Streaming drawing counters also matched, and its allocation slopes did not increase. Loading the plugin and its public modules added 93,632 bytes of constant live memory in the standalone frame harness. These measurements predate the normal-mode shortcut change. Its keyboard timing has not had a separate comparison. The benchmark build copies were removed; the JSON reports remain in `/tmp/yuke-dashboard-bench.Vfs6Pr/`.

## Check

The checks require Python 3, tmux, and an installed Yuke binary. Set `YUKE_TEST_BINARY` to the absolute path of another build to test that build.

```sh
python3 ~/.config/yuke/tests/check-yuke-dashboard.py
YUKE_DASHBOARD_MINIMAL_PROFILE=1 python3 ~/.config/yuke/tests/check-yuke-dashboard.py
YUKE_DASHBOARD_FULL_PROFILE=1 python3 ~/.config/yuke/tests/check-yuke-dashboard.py
yuke check
```

The focused check uses a private detached tmux server, temporary XDG directories, the real Vim editing plugin, and a loopback model provider. It imports the real dashboard. It checks startup normal mode, letter actions, insert-mode typing, removal of Alt bindings, optional actions, unload/reload, model selection, mouse actions, command and session menus, first send, resume, split panes, compact layout, search, work, modal routing, and both exit paths. It also checks mode retention across pane focus, new drafts with unchanged null IDs, pending Vim operators, transcript focus, and title/hint ownership during unload.

The minimal-profile variant loads only the dashboard and bundled Composer Vim. It checks startup mode, a new empty draft, model selection, commands, insert typing, the first prompt, and exit. It does not require the custom Vim, search, or work plugins.

The full-profile variant checks startup actions, modes, typing, unload/reload, model selection, and the first prompt with the actual profile loaded. It stops after that prompt and verifies exit. It does not check the full profile's session ownership or resume behavior.

For a focused type check, use the declarations from the installed binary:

```sh
tsc --allowJs --checkJs --noEmit --strict --module esnext \
  --moduleResolution bundler --target es2022 --lib es2025 \
  ~/.config/yuke/yuke.d.ts ~/.config/yuke/yuke-modules.d.ts \
  ~/.config/yuke/plugins/yuke-dashboard.js
```

All three checks save labeled screen captures and close their test server. They do not attach to tmux, read real sessions, use the clipboard, or send a request to a remote model.
