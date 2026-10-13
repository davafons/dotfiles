# Changelog

## Unreleased

- Add bundled `/pwd` to show the current workspace. Keep the conversation and unsent draft unchanged. After `/cd`, report the destination workspace.

- Add directory-only completion for `/cd`, including empty arguments, relative paths, home paths, and the filesystem root. Keep Tab and Enter as completion keys. Quote paths with spaces. The command needs the native workspace-aware build.

- Show the xAI weekly usage pool in `/status`. The bar is the share left in the current pool, not a remaining-token balance. A missing percentage stays unknown. Press `d` for product shares. The reader uses the stored `xai-grok` login and makes no model call.

- Load the empty-session dashboard from the published `lostcoords/yuke-plugins` commit. The menu is sign-in, sessions, search, work, model, commands, and quit. Sign-in is `l`. Assigned letters run those rows before Vim. The menu is configured from `dashboard-config` through `setup`. Remove the duplicated dashboard folder from the dotfiles.

- Load Solarized from the published `lostcoords/yuke-plugins` commit. Remove the duplicated theme folder from the dotfiles and ignore the GitHub source cache.

- Add a fresh `reviewer` child role on Codex GPT-6.1 Sol at `xhigh`. Preserve general and dav-agent defaults. Save engine model receipts in spawn results and log child request models. Verify native routing, stored settings, request payloads, depth limits, and project skill discovery with private scripted-provider fixtures. These fixtures do not prove model judgment or different-family review.

- Report pending clarification questions to Herdr as blocked. Use Herdr's normal needs-attention notifications for single questions and batches. Keep question state in the inbox plugin and external reporting in the Herdr plugin. Preserve pending state through reload and clear it after resolution. Verify the visible notification with a private Herdr server and muted detached client.

- Add the `fork_session` model tool over native `session.fork`. Return an independent conversation ID and `yuke resume` command for Herdr. Reload destination instructions and skills without moving the source or copying its active run, queue, children, or jobs. Requires the workspace-aware fork build; keep normal activation separate from source preparation.

- Move live timing to the end of the response after thoughts and tool output. Use verb headings with "model response" and short h/m/s durations. Freeze intermediate completed observations in place. Hide only the final timing summary when the run ends. Keep thought and tool durations visible. Label hidden-thought estimates with `~` and explain their observed waiting-time basis. Preserve native history, source copying, grouping, and live reasoning identity.

- Show `thought · time unavailable` for a completed hidden-only reasoning block whose measured duration rounds to zero. Preserve real visible reasoning clocks and stored replay data. Add a native encrypted-only Responses regression.

- Move detailed phase timings from the prompt strip into display-only blocks beside model responses. Use one thought-style heading with a clock mark, the current phase, and total elapsed time. A click or Ctrl+O expands the phase breakdown. Keep observed phases after the run ends without adding engine messages or model context. Rename the phase label "responding" to "reading model response" and document the coarse activity states. Reload clears these temporary observations.

- Consolidate model controls and effort status into `models`, basic controls into `controls`, live timing and speed into `run-feedback`, and inspection views into `insights`. Add per-feature settings, model shortcuts, and feedback intervals. Share accepted model state, an idle-aware feedback clock, and lazy inspection setup. Keep diagnostic tracing off by default and leave the pinned xyaman Vim implementation unchanged. See `CONFIGURATION.md`.

- Shorten the bottom build label and `/status` Build row to an eight-character revision without the build timestamp. Keep the full embedded version in `yuke --version`, RPC, and request metadata.

- Start Herdr reporting after the interactive UI is ready. Restore missing Yuke sidebar agents at startup and after native reload. Add a private-server regression for reporting, approvals, reload, quit, and parent-pane safety.

- Port `/loop` to manifests and current engine drains. Read root turn outcomes explicitly so failure and cancellation pause schedules. Cache status counts. Add a native loopback guard for delivery, stop, and reload cleanup.
- Add the optional `/peek` profile entry for frozen read-only progress snapshots and observer-only cancellation. Show captured activity, completed-turn outcomes, check exit codes, recorded diff excerpts, recent actions, and errors separately from the model's summary. Compare visible records on refresh without reading the worktree or messaging the worker.
- Show observed native or Herdr activity on `/work` task cards. Follow the latest linked checkpoint without changing the saved task stage. Poll only while the dialog is open. Animate cached marker text.
- Refresh dashboard action availability after plugin startup so Search and Work appear on the first screen. Document manifest reuse, command dependencies, and reload ownership in `DASHBOARD.md`.
- Bound matching chat previews by characters as well as FTS tokens. Keep a match visible after a long token. Port work, alias, clarification, and search storage guards to the canonical manifest profile.

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
