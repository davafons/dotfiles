# Changelog

## Unreleased

- Promote the verified 28-plugin manifest profile to `.config/yuke`. Use native reload and pinned Vim. Remove the old factory loader and one-time switch scripts. Keep pre-manifest tests and guides as references outside deployment. Preserve the unfinished loop source as disabled experimental code. Document the fresh-store cutover and the approved retired-data cleanup.

- Added `/status` with a compact, account-first card. Solid Unicode bars show remaining allowances in green, amber, or red; cyan shows free context space. Press `d` for build, session, authentication, token breakdown, and cost details. Codex login reports timed allowances, reset times, plan, and credits. OpenRouter reports its key spending cap and free-model requests. Missing quotas stay unknown; credits and context space are not remaining account tokens. The main card omits missing-5h notices and credit explanations. Footer hints have color and omit `j/k`; expanded details use distinct colors for models, authentication, tokens, and unpriced costs. Blank rows separate the allowance, credits, context, and diagnostic groups. The lazy view fits its content, preserves drafts, and cancels its reader on close. Reads make no model call. See `STATUS.md`.

- `/context` now places its 200-square grid on the left and its legend on the right. Narrow dialogs stack the grid above the legend and use the full available width. Counts and category proportions stay unchanged. Fixed PageUp and PageDown scrolling.

- `/context` keeps saved prompt colors after reload instead of hiding the whole split. Add Skills and Tools tabs with per-definition bytes, token estimates, and occupied-context shares. Add `v` to scale the grid to the saved prompt budget. Live registered tool inspection requires the updated Yuke core; it does not claim historical request attribution.

- `/model` now shows one row per model, with a star and alias badge for favorites instead of separate alias rows. Ctrl+A sets or renames an alias, Ctrl+E sets its default effort, and Ctrl+R removes it. Edits persist across reload and restart, update slash commands immediately, and use revision-checked atomic writes. Alias edits keep the current model and draft. See `MODELS.md`.

- Reworked `/context` as a profile-owned dashboard with a 200-square color grid, a category legend, and Overview/Details tabs. It separates system instructions, AGENTS.md, skill summaries, estimated tool/request overhead, chat, free space, and the safety reserve. It keeps the built-in status bar, preserves drafts, and restores the original command on unload. Reads run only on open or refresh. Token estimates and unavailable splits have explicit labels. See `CONTEXT.md`.

- Selecting a row in `/model` now opens that model's numbered effort picker. The choice applies only after effort confirmation; Escape keeps the previous model. Favorites suggest their configured effort. Direct aliases and argument commands still apply immediately.

- Simplified `/search` to All, Chats, and Files. Matching passages now come first, and long-message quotes retain the match. Added palette colors for sources, highlighted preview terms, progress, and errors. A chat that changes during indexing retries automatically instead of showing as unindexable. Real failures show their cause.

- Added `model-manager` with separate `/model` and `/effort` controls, numbered pickers, favorite presets at the top of the `/model` picker, configurable slash aliases, and optional preset shortcuts. Ctrl+X then M opens models; Ctrl+X then E opens effort. `/sh` selects newest Sol/high and `/lm` selects newest Luna/medium on `openai-codex`; Ctrl+X then S/L selects them directly. Family presets compare numeric versions and refresh from the catalog. Direct model commands retain supported session effort. Interactive selection asks for effort before applying the model. Unsupported presets keep the current choice. See `MODELS.md` for configuration and checks.

- Enable the bundled `pathCompletion` plugin in the reloadable profile. In composer insert mode, `./`, `../`, `~/`, and directory paths open a completion menu. Tab or Enter inserts a match without sending. Bare slash words remain commands. The cache and Vim mode fixes require the updated Yuke build and a restart.

- Fixed native metadata for inline and multiple `$skill-name` invocations. The engine now loads and saves their bodies. The transcript folds the bodies without hiding the original message. `/usage` counts each invocation and groups steering messages under their active run. This fix requires the updated Yuke core and a restart.

- Reviewed dashboard lifecycle behavior. Returning to an empty pane now preserves its selected Vim mode. Ctrl+N starts in normal mode even when the previous draft was also empty. Unloading preserves title and hint replacements from other plugins. Detached-TUI regression checks cover these cases.
- Added `yuke-dashboard` for empty sessions. A centered YUKE header shows the workspace, model, and clickable startup actions. Empty drafts start in normal mode. `r` resumes a session, `s` opens search, `w` opens project work, `m` selects a model, `c` opens commands, and `q` exits. `i` enters insert mode; Esc returns to normal mode. Action letters type text in insert mode and keep their Vim meaning in nonempty drafts. The dashboard has no Alt bindings. It adapts to small panes and leaves saved transcripts unchanged. See `DASHBOARD.md`.

- Added `/search`, a native two-panel finder for session titles, saved user/assistant text, file paths, and workspace file content. Search has workspace/all-session scope, source filters, previews, draft-safe quote/path insertion, and ownership-safe Herdr navigation. A private, rebuildable index reuses unchanged histories. See `SEARCH.md` for controls and limits.

- Added a read-only GitHub outer loop to `/work` and the `github_work` tool. Browse issues and PRs, review and CI state, cursor pages, and explanations below the list. Link internal tasks with `github_url` or capture a step from a GitHub item. Internal completion never changes GitHub state. Reads use `gh` authentication and stop when the view closes. No comments, closing, pushing, or merging.

- Added `/work`, `/todo`, `/checkpoint`, and the `project_work` agent tool. Tasks, project goals, and session checkpoints persist across restarts and linked checkouts. The full-screen view follows `/usage`, with full-width colored kanban columns, explanations below the cards, Context and Checkpoints tabs, filtering, mouse controls, and a one-column layout for narrow terminals. Work views preserve drafts, prepare briefs without sending them, and open linked sessions. Later run starts mark older checkpoints stale. Version checks protect concurrent task and context edits. See `WORK.md` for limits and checks.

- Fixed `$skill-name` completion after `/reload` updates the session context. Ctrl+A and Ctrl+E now close the skill menu and move the caret, so the next Enter sends the draft.

- Added `!command` to the composer. Commands run directly in the workspace. Results stay in the transcript and enter the model context on the next requested turn, as in Codex. `!sudo` reuses command approval and masked password retries. Ctrl+C stops a direct command. The prefix requires the new Yuke build and a restart.

- Added `$skill-name` invocation in chat. `$` opens a skill menu. Tab or Enter inserts a name without sending the draft. A send loads each named skill once, including inline mentions and multiple skills. Code spans and escaped dollars stay literal. Workspace skills override global skills. Existing sessions use their stored catalog. An unreadable skill blocks the send and restores the draft.

- `sudo_command` now reopens the masked password dialog when sudo requests another attempt. Retries stay in one tool call and one sudo process. Sudo controls the attempt limit. The command never restarts after a command failure. Cancellation and deadlines close an open retry dialog.

- Added `sudo_command` with per-command approval and a masked password dialog. A private askpass helper keeps password bytes off command stdin, arguments, environment variables, files, logs, and model results. The tool returns bounded output and exit status. See `SUDO.md` for limits and checks.

- Click the questions banner above the prompt to open the clarification inbox. Opening it preserves the unsent draft, caret, and Vim mode. Hotkeys and `/questions` still work.

- Added `/exit` and `/close` to close Yuke through its graceful quit API. Both commands respect existing quit guards and appear in the command palette.

- Added multi-select clarification questions with checkboxes, number/Space toggles, custom answers, and notes alongside choices. Added `request_user_input` question batches with stable IDs, local staging, review/edit controls, explicit unanswered confirmation, and one combined answer delivery. Both flows retain drafts across reloads and use transactional submission claims.

- `Ctrl+H` now opens pending clarifications like `Shift+Left`, retaining left-panel navigation when the chat has no questions. Selected response labels and descriptions now use a solid accent-colored highlight with contrasting text.

- `/sessions` now marks sessions mapped to another Herdr pane in cyan (`↗ ELSEWHERE`). Click the row or press Enter to jump to its owning pane instead of trying to resume it locally. Sessions with no reported pane remain protected.

- Added the running Yuke build to the bottom status bar. The label comes from the engine's embedded version, so installing a new binary does not make an old process appear current. Local builds now include the source revision and UTC build time.

- Percentage breakdowns in `/usage` now use parentheses, for example `1,180,000 (79.7%)`, instead of a dot separator.

- Added consumption percentages to `/usage`: cache reads/writes and uncached input as shares of input, input/output as shares of total tokens, reasoning as a share of output, and cache savings relative to estimated no-cache cost. Provider/model and period tables show weighted cache-read rates.

- Added semantic colors to `/usage`: blue headings and navigation, cyan token counts and tools, violet reasoning and skills, green savings and healthy states, amber costs and incomplete data, and red failures. Chat metadata is split into colored fields.

- Added `/usage`, a Codex-style dashboard with six tabs, a yearly token heatmap, global/workspace filtering, token and cost breakdowns, provider/model statistics, tool and skill rankings, and searchable chats with resume controls.
