# Desired yuke keymap changes

This file records requested key behavior. It does not register bindings.
Keep changes in profile plugins. Do not change the core without approval.
Use `/reload` after a plugin code change. Restart only after changing the stable `index.js` or `profile-reloader.js` loader.

## Implemented

### Provider status (`status`)

- `/status` opens a compact card with account allowance first. Solid bars show remaining limits in green, amber, or red. Cyan shows context space and numeric values.
- Codex login reports remaining timed allowances, reset times, and credits. OpenRouter reports the key spending cap and free requests. Other providers show account quota as unavailable.
- `d` shows or hides colored build, session, authentication, usage, and cost details. `r` refreshes. Arrows, page keys, Ctrl+D/Ctrl+U, Home/End, and the wheel scroll. Escape, Ctrl+C, or `q` closes the card without changing the draft. The footer shows colored refresh, details, and close hints.
- Reads make no model call. Credits, session tokens, and context space remain separate. See `../../STATUS.md` for provider support, security, and checks.

### Model and effort manager

- `/model` shows one row per model, with favorites first. Rows use model names, not separate `/sh` or `/lm` entries. A star and alias badge mark each favorite.
- Number keys 1–9 select a row. Text filtering renumbers results. Selecting a model opens its effort picker; Escape keeps the previous model. Direct aliases and `/model` arguments still apply immediately.
- In the model list, Ctrl+A sets or renames an alias. Blank removes it. Ctrl+R removes it after confirmation. Ctrl+E sets its default effort. These edits do not change the session model or draft.
- Aliases are favorites. Edits save across reloads and restarts, register slash commands immediately, and reject duplicates. Removing an alias also removes its shortcut; it never removes the model.
- `/effort` opens numbered effort choices for the current model. `/effort medium` or `/effort 2` changes only effort.
- Ctrl+X then M opens models. Ctrl+X then E opens effort. The initial Ctrl+X S/L shortcuts select newest Sol/high and Luna/medium on `openai-codex`.
- See `../../MODELS.md` for saved settings, initial defaults, and isolated checks.

### Empty-session dashboard (`yuke-dashboard`)

- Show a centered YUKE logo, workspace, model, and startup actions in each draft pane. An empty draft starts in normal mode.
- In an empty normal-mode composer, `r` resumes a session, `s` opens search, `w` opens project work, `m` selects a model, `c` opens commands, and `q` exits through the normal quit guards.
- Press `i` to type a prompt. Esc returns to normal mode. Insert mode types the action letters. Nonempty drafts keep their Vim editing keys. The dashboard has no Alt bindings.
- Click an action to run it. Optional search and work rows appear only when those plugins are loaded. Modal dialogs keep their keys.
- `/new`, `/clear`, and Ctrl+N return to the dashboard. Saved conversations keep their normal transcript.
- Use `/reload` or restart to load the plugin. Check with `python3 ~/.config/yuke/tests/check-yuke-dashboard.py`. See `DASHBOARD.md` for menu and theme changes.

### Path completion (`path-completion`)

- In composer insert mode, type `./`, `../`, `~/`, or a directory path to show its entries. Bare `/` and `/word` remain command input.
- Up/Down or `Ctrl+P`/`Ctrl+N` selects a match. Tab or Enter inserts the match without sending. A directory gets a trailing `/` and opens its entries.
- Left/Right reuses the directory list. Escape or a switch to normal mode closes the menu.
- The profile enables this bundled plugin. Restart after installing an updated Yuke build; `/reload` cannot replace code inside the executable.

### Vim status on the left

- Show the existing `NORMAL` and `INSERT` mode indicators on the left.
- Show editing status, including `VISUAL`, `VISUAL LINE`, and `REPLACE`, on the left.
- Keep one copy of each indicator and track the focused pane.
- Keep other status entries on their current side.

### `$skill-name`: invoke skills in chat

- Type `$` or a name prefix to list matching skills above the composer.
- Up/Down or `Ctrl+P`/`Ctrl+N` selects a skill. Tab or Enter inserts its name. Enter does not send while the menu is open.
- Escape closes the menu. A later text edit can open it again.
- Left/Right, Home/End, and Ctrl+A/Ctrl+E close the menu and move the caret. The next Enter sends the draft.
- Send `$tdd fix this` or `Use $tdd and $yuke to fix this`. The plugin requests each referenced skill once. The engine loads its body before the message reaches the model.
- Workspace skills override global skills. Existing sessions use their stored catalog. `/reload` updates the profile and the current session catalog.
- Unknown names, dollar amounts, backtick code spans, and escaped dollars such as `\$tdd` stay literal.
- Skill reads use canonical paths. Relative paths in a skill resolve against its source directory.
- The transcript folds skill bodies and keeps the original message visible. `/usage` counts each native invocation, including messages that steer an active run.
- An unreadable skill or a skill file above 256 KiB blocks the send and restores the draft. Draft catalog output above 64 KiB disables completion.
- Native metadata requires the updated Yuke core. Build and install it with `mise run install` in the Yuke source checkout. Restart Yuke after the install.
- Check with `python3 ~/.config/yuke/tests/check-dollar-skills.py`. The test uses a detached tmux server, temporary skill roots, and a loopback provider.

### `/clear`: start a new chat

- `/clear` delegates to the built-in `/new` command.
- It leaves the current session and opens an empty draft in the same pane.

### `/exit` and `/close`: close Yuke

- `/exit` and `/close` request a graceful exit through the same quit API as `Ctrl+Q`.
- Existing quit guards can hold the exit while work is running.
- It also appears as `exit Yuke` in the command palette.

### Native search

- `/search` or `/search words` opens a separate native finder for sessions, saved chat text, file paths, and workspace file content.
- `Tab` switches workspace/all-session scope. `Ctrl+T` switches All, Chats, and Files. `Ctrl+R` refreshes the index and file paths.
- `Ctrl+P`/`Ctrl+N` selects results. `Ctrl+D`/`Ctrl+U` scrolls the preview.
- Enter opens a session or focuses its Herdr owner. A file result inserts its path. `Ctrl+Y` inserts a previewed quote or path without sending the draft.
- Matching passages come first. Long previews start near the match. Chat/file badges and matched preview terms use theme colors.
- A chat that changes while search reads it retries automatically. Real errors show their cause.
- Escape or Ctrl+C closes search without changing the draft. Ctrl+F keeps the session browser.
- See [`../../SEARCH.md`](../../SEARCH.md) for matching rules, cache privacy, limits, and checks.

### Session browser

- `/sessions` opens a wide fuzzy finder for root sessions and forks. Each row is labeled `current`, `open here`, `open elsewhere`, or `closed`.
- Sessions open in another Yuke remain visible for inspection but cannot be resumed with Enter or a mouse click. Closed sessions remain resumable.
- `/resume` delegates to `/sessions`.
- The browser starts in the current session's workspace, or Yuke's launch folder for a fresh draft.
- `Tab` toggles between the current workspace and all workspaces.
- `/sessions all` opens all workspaces directly.
- The left panel uses three-row entries: state and title/context, latest user prompt, then workspace/model/message metadata.
- Generic titles such as `yuke` are replaced visually by the latest user-prompt excerpt, while the original title remains on the context row.
- Current, working, open-elsewhere, and closed entries use distinct labels and colors.
- Recent prompt context loads concurrently for the newest 50 sessions; preview and context share one history request.
- Sessions use newest-update order. Equal update times use creation time and session ID for a stable order.
- The right panel uses the chat renderer to preview the last user prompt and the messages after it, initially scrolled to the newest message at the bottom.
- `Ctrl+N` and `Ctrl+P` move through the filtered sessions. Enter resumes the selected session.
- `Ctrl+D` and `Ctrl+U` scroll the preview. The mouse can scroll or expand its tool blocks.

### Background clarification inbox (`yuke-clarify`)

- `ask_question` queues one question; `request_user_input` queues a related batch of 1–3 questions. Neither opens a popup or waits for an answer.
- Pending questions for the focused chat appear in a framed `1)`, `2)`, `3)` stack above the prompt, plus `3 questions · ⇧←` in the left status bar. Existing queued-input and working-prompt rows stay intact.
- The picker also numbers its response choices and fits its height to the content. Question headings, recommendations, descriptions, and the selected option have theme-aware colors and highlights.
- `Shift+Left` and `Ctrl+H` open the inbox from composer insert/normal mode or transcript focus. `Ctrl+H` takes precedence over pane navigation only while that chat has unresolved questions. Modal dialogs keep their keys. `/questions` is the fallback.
- Arrows and `j`/`k` move between options. Number keys select single choices or toggle multi-select checkboxes. Space toggles a checkbox; Backspace/Delete clears checkboxes. Enter confirms. `Other…` supports a custom answer alongside checked choices.
- `Ctrl+E` or typing from choices opens notes; `Ctrl+B` returns to choices. In batches, Tab switches choices/notes and `Ctrl+P`/`Ctrl+N` or Left/Right navigate questions.
- In a batch, Enter stages the answer without sending it. The last question opens review; `1`–`3` edit questions and Enter submits one combined input. Unanswered questions require explicit confirmation and never choose a default.
- In the answer editor, `Shift+Enter` and `Ctrl+J` insert a newline.
- In standalone questions, `Tab`/`Shift+Tab` move between questions and retain unfinished answer drafts. `PageUp`/`PageDown` scroll long question/context text.
- Escape or `Ctrl+C` closes the inbox and leaves questions pending. `Ctrl+D`, then Enter, explicitly declines a question; Escape cancels the decline.
- Answers go directly to the originating session, without modifying the chat composer, its caret, attachments, or Vim mode.
- Questions and answer drafts persist across restart and profile reload. Transactional claims prevent concurrent duplicate submissions.
- A send interrupted by a process crash is marked in progress/uncertain, not automatically retried.
- See [`../../CLARIFY.md`](../../CLARIFY.md) for the model contract, storage, and focused checks.

### Panel and region navigation

- `Tab` toggles between the prompt bar and message history in the active panel.
- `Ctrl+H` moves to the panel on the left when the focused chat has no unresolved clarifications; otherwise it opens the question inbox. `Ctrl+L` moves to the panel on the right.
- In transcript focus, `Ctrl+K` and `Ctrl+J` move to the panel above or below.
- In prompt insert mode, `Ctrl+J` inserts a newline unless `Ctrl+K` has started sent-prompt history. Use `Tab`, then `Ctrl+J`, to move to a panel below.
- In the prompt, `Ctrl+K` moves to an older sent prompt and `Ctrl+J` moves newer once history is active, instead of moving between panels.

### Composer newlines

- In composer insert mode, `Shift+Enter` and `Ctrl+J` insert a newline without submitting.
- Tmux preserves Ghostty modified named keys with its extended-key protocol.

### Prompt history and active prompt

- In the composer, `Up` and `Down` navigate sent prompts when the caret cannot move farther vertically. This works in insert and normal mode without replacing multiline arrow movement.
- `Ctrl+K` moves to an older prompt in insert or normal mode. Once history is active, `Ctrl+J` moves toward newer prompts; otherwise insert-mode `Ctrl+J` remains newline.
- `/history` opens a searchable newest-first picker of every sent prompt in the current chat. `Ctrl+J`/`Ctrl+K` move through results, and Enter restores the selected full prompt in normal mode.
- Recalling a sent prompt reconstructs its image attachments as real composer image spans, including picker selection.
- Moving forward past the newest sent prompt restores the exact unsent draft, including attachments, that was present before history navigation.
- Editing a recalled prompt leaves history navigation and makes the edited text the current draft.
- While a session is working, one dimmed `working` row below any queued-input rows summarizes the prompt currently being processed.

### `Ctrl+C`: clear or exit

- With composer content in insert or normal mode, clear the complete composer and enter normal mode.
- With an empty composer in insert mode, enter normal mode.
- With an empty composer in normal mode, interrupt the session and show `press Ctrl+C again to exit`.
- Press `Ctrl+C` again without another action to request exit.
- Leave modal dialogs in control of `Ctrl+C`.

### `/`: start a command

- In composer normal mode, `/` enters insert mode and inserts `/` at the caret.
- In transcript focus, `/` focuses the composer, enters insert mode, and inserts `/` at the caret.
- Preserve the existing draft.
- In insert mode, `/` stays ordinary text input.
- Leave modal dialogs in control of their keys.

### Composer motions and counts

| Keys | Behavior |
|---|---|
| `h`, `l`, arrows | Move by graphemes. |
| `j`, `k` | Move by drawn rows. Operators use logical lines. |
| `0`, `^`, `$` | Move to line start, first nonblank, or line end. |
| `w`, `b`, `e` | Move by words. Punctuation has its own word class. |
| `W`, `B`, `E` | Move by whitespace-separated WORDs. |
| `ge`, `gE` | Move to the previous word or WORD end. |
| `gg`, `G` | Move to the first or last line. A count selects a line. |
| `f<char>`, `F<char>` | Find a grapheme forward or backward on the current line. |
| `t<char>`, `T<char>` | Move to the position before or after the found grapheme. |
| `;`, `,` | Repeat the saved find in its original or reverse direction. |
| `%` | Match parentheses, square brackets, or braces. Skip quoted strings and escaped delimiters. |
| `<count>%` | Move to that percentage of the draft's lines. Use a count from 1 to 100. |
| `{`, `}` | Move to a paragraph boundary. Empty lines separate paragraphs. |

Counts apply to motions and operators: `3w`, `2b`, `3dd`, `d2w`, `2dw`, and `2d2w`.
Counts before and after an operator multiply.
Counts also apply to insertion, put, undo, redo, and repeat: `3i`, `3o`, `2p`, `2u`, and `2.`.
The count limit is 10,000. An invalid large count cancels the pending command.

### Operators and text objects

- `d`, `c`, `y`, `gu`, `gU`, `g~`, `>`, and `<` accept the listed motions.
- `dd`, `cc`, and `yy` act on whole lines.
- `dw` leaves the final line break in place.
- `cw` and `cW` leave following whitespace in place when the caret starts on text.
- Change operators enter insert mode.
- `x`, `X`, `s`, `S`, `D`, `C`, and `Y` use the same profile-owned register.
- `X` deletes backward. `S` changes whole lines. `Y` yanks whole lines.
- `p` and `P` put characterwise or linewise text from that register.
- Native transcript yank events update that register too.
- Operators, counts, character finds, and text-object prefixes wait without a timeout.
- Escape or a focus change cancels a pending command.
- Control-key shortcuts still work while an operator waits.

| Text objects | Meaning |
|---|---|
| `iw`, `aw` | Inner word, or word with adjacent whitespace. |
| `iW`, `aW` | Inner WORD, or WORD with adjacent whitespace. |
| `i"`, `a"`, `i'`, `a'`, `` i` ``, `` a` `` | Inner or surrounding quoted string on the current line. Escaped quotes do not close it. |
| `i(`, `a(`, `i)`, `a)`, `ib`, `ab` | Inner or surrounding parentheses. |
| `i[`, `a[`, `i]`, `a]` | Inner or surrounding square brackets. |
| `i{`, `a{`, `i}`, `a}`, `iB`, `aB` | Inner or surrounding braces. |

Examples: `ci"`, `da'`, `di(`, `ci{`, `yi[`, and `d2i(`.
A bracket-object count selects an outer enclosing pair.
As in Vim, `2i"` includes the quotes without surrounding whitespace. A count does not extend `a"` to another quoted string.

### Replacement, joins, case, and indentation

| Keys | Behavior |
|---|---|
| `r<char>` | Replace one grapheme without insert mode. A count replaces that many graphemes. An insufficient line length leaves the text intact. |
| `R` | Type over existing graphemes. Append at line end. Backspace restores the overwritten grapheme and span metadata. Escape ends replacement. |
| `J`, `gJ` | Join logical lines. `J` removes following indentation and uses one separating space. `gJ` preserves whitespace. A count selects the number of lines, with a minimum of two. |
| `~` | Toggle case and move forward. A count selects graphemes. |
| `gu`, `gU`, `g~` | Make a motion range lowercase, uppercase, or toggle case. Examples: `gUiw`, `guw`, and `g~aw`. |
| `guu`, `gUU`, `g~~` | Change case on whole logical lines. A count selects lines. |
| `>`, `<` | Shift logical lines right or left by two spaces. Examples: `>>`, `<<`, `>j`, and `<i{`. |

Indentation uses two-space units, two-cell tab stops, and spaces in the result.
A count on `2>>` selects two lines. A count on a visual shift, such as `3>`, selects three shift units.
Case changes use JavaScript Unicode case mapping. This can expand a character.
`R` ends when composer focus changes. It then uses ordinary insert mode.
Composer submit and newline bindings stay unchanged in `R`.
Counts, undo, redo, and `.` work with these edits.

### Registers

- `"a` through `"z` select a named register for the next command.
- An uppercase name appends: `"Ayy` appends a line to register `a`.
- `"0` holds the last unnamed yank.
- `"1` through `"9` hold line or multiline delete history.
- `"-` holds the last unnamed small delete.
- `"_` discards a delete or yank without changing registers.
- `""` selects the unnamed register.
- In insert mode, `Ctrl+R` then a register name inserts its text.
- Examples: `"ayy`, `"ap`, `"_diw`, and `"0P`.
- Named transcript yanks also update these registers. Transcript motion and selection stay native.
- Registers belong to the profile instance. They survive a replacement draft and work across panes.
- Clipboard registers `"+` and `"*` are not implemented. Plugin code does not access the desktop clipboard.

### Local marks and draft search

| Keys | Behavior |
|---|---|
| `ma` through `mz` | Set a local composer mark. |
| `` `a `` | Jump to the marked position. |
| `'a` | Jump to the first nonblank of the marked line. |
| `Alt+/` | Open a literal, case-sensitive draft search prompt. `/` stays the command shortcut. |
| `n`, `N` | Repeat the saved search direction or its reverse. Counts work. Search wraps. |
| `*`, `#` | Search forward or backward for the keyword under or after the caret on this line. Match a whole keyword. |
| `g*`, `g#` | Search for the same text without keyword boundaries. |

Mark jumps and search repeats also work as operator motions, such as `d'a`, `` d`a ``, and `dn`.
Marks belong to each composer. A replacement draft clears them. Undo restores saved marks.
Marks keep their column during a same-line edit, as in Vim. Line edits move them.
Search does not put the caret inside a grapheme. A cancel or missing result preserves the text and caret.
An empty search answer repeats the previous query.
Search applies to the composer, not the transcript. Regular expressions and global marks are not implemented.

### Composer visual mode

- `v` starts characterwise selection.
- `V` starts linewise selection.
- Motion keys and text objects change the selection.
- `o` exchanges the selection ends.
- `d`, `c`, `y`, `r<char>`, `u`, `U`, `~`, `>`, `<`, `J`, and `gJ` act on the selection.
- `p` replaces the selection and saves the replaced text in the unnamed register.
- `P` replaces the selection without changing the unnamed register.
- `gv` restores the previous selection.
- Visual `P` repeat uses the saved selection size and the current source register. Native headless Vim can produce a delete-only repeat for this command. The profile follows the documented replacement behavior instead.
- Escape cancels the selection.
- The composer highlights selected text. The status shows `VISUAL` or `VISUAL LINE`.

### Undo, redo, and repeat

- `u` undoes a change group.
- `Ctrl+R` redoes a change group in normal mode.
- One insert session forms one group.
- A change operator and its inserted replacement form one group.
- Undo and redo restore caret positions and composer span metadata.
- A new edit clears redo history.
- History belongs to each composer. A replacement draft or a successful submit clears it.
- History keeps at most 100 groups and about 1 MiB of text characters. It keeps the newest group even if that group exceeds the text budget.
- `.` repeats the last change, including typed replacement text.
- A count on `.` replaces the saved count.
- A repeated change forms one undo group.
- Repeat preserves current text between separate insert edits.
- Repeat does not recreate image attachments. An insert change in a draft with images clears the saved repeat command. Undo and redo still preserve image metadata.

### Transcript WORD motions

- `W` and `B` move by WORDs across rendered rows.
- Counts work with WORD motions and basic transcript motions.
- The bundled transcript plugin still owns its cursor, visual selection, source anchors, and scrolling.
- These motions also work in transcript visual mode.

## Implementation

`plugins/vim-improved.js` loads these helpers:

- `vim-operators.js`: composer grammar, operators, visual selection, history, and repeat.
- `vim-text.js`: grapheme-safe text navigation and text objects.
- `vim-edits.js`: replacement, joins, case mapping, and indentation plans.
- `vim-transcript.js`: transcript WORD motions through native motion handlers.

The host does not expose its Vim register. The plugin keeps its own register.
Registration uses block-owned APIs. Dispatch advice and pending writes use the inherited shared registry.
Do not load a second composer Vim operator replacement with this plugin.
Plugin code does not read or write the desktop clipboard. Native transcript yank behavior stays unchanged.

References:

- [PR #2: support `dw` in composer normal mode](https://github.com/lostcoords/yuke/pull/2).
- [PR #5: complete composer Vim operators and chord handling](https://github.com/lostcoords/yuke/pull/5).

These profile changes do not apply either core PR.

## Pending requested changes

None recorded.
This is the requested Vim subset, not a complete Vim implementation.
`/` remains the command shortcut. `Alt+/` searches the composer.
Macros, blockwise visual selection, language-aware reindent, Ex commands, and transcript search are not implemented.

## Verification

```sh
tsc -p ~/.config/yuke/jsconfig.json
python3 ~/.config/yuke/tests/check-clear-alias.py
python3 ~/.config/yuke/tests/check-exit-command.py
python3 ~/.config/yuke/tests/check-ctrl-c.py
python3 ~/.config/yuke/tests/check-composer-newlines.py
python3 ~/.config/yuke/tests/check-panel-navigation.py
python3 ~/.config/yuke/tests/check-prompt-history.py
python3 ~/.config/yuke/tests/check-sessions-reworked.py
python3 ~/.config/yuke/tests/check-search-store.py
python3 ~/.config/yuke/tests/check-search-tui.py
bash ~/.config/yuke/tests/run-vim-operators.sh
python3 ~/.config/yuke/tests/check-vim-parity.py
python3 ~/.config/yuke/tests/check-vim-render.py
python3 ~/.config/yuke/tests/check-vim-search.py
yuke check
```

The key checks use an isolated profile and session store.
The native comparison checks 105 text results and 101 caret results. Undo and redo keep profile snapshot caret semantics.
Transcript register checks simulate native yank events without accessing the desktop clipboard.
The render and search-dialog checks use isolated pseudo-terminals. It saves ANSI output and checks the selection style.
No check activates a desktop application, sends desktop keys, or plays audio.

For each new request, record the key, focus or mode, desired action, and status.

## Performance check

`tests/measure-vim.py --base <saved-plugins-directory>` compares both profile versions in isolated pseudo-terminals.
It alternates six runs per version. Each run uses 30,000 iterations per phase after warmup.
The latest lowest-quartile wall times were:

| Phase | Previous plugin | Current plugin | Change |
|---|---:|---:|---:|
| Word motion pair | 1,417 ms | 1,276 ms | -10.0% |
| Type and backspace pair | 616 ms | 626 ms | +1.6% |
| Delete and grouped insert | 2,912 ms | 2,985 ms | +2.5% |
| Cached draw | 129 ms | 129 ms | 0% |
| Cached visual draw | 154 ms | 153 ms | -0.6% |

All five phases had the same measured retained-heap change on both versions.
Wall time has about 20% noise. These measurements do not prove zero cost for a small change.
The check does not count cumulative allocations or instructions. Valgrind is not available on this host.
