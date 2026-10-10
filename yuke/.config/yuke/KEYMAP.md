# Desired yuke keymap changes

This file records requested key behavior. It does not register bindings.
Keep changes in profile plugins. Do not change the core without approval.
Use `/reload` after a plugin code change. Restart only after changing the stable `index.js` or `profile-reloader.js` loader.

## Implemented

### Vim status on the left

- Show the existing `NORMAL` and `INSERT` mode indicators on the left.
- Show editing status, including `VISUAL`, `VISUAL LINE`, and `REPLACE`, on the left.
- Keep one copy of each indicator and track the focused pane.
- Keep other status entries on their current side.

### `/clear`: start a new chat

- `/clear` delegates to the built-in `/new` command.
- It leaves the current session and opens an empty draft in the same pane.

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

- The agent's `ask_question` tool queues a question without opening a popup or waiting for an answer.
- Pending questions for the focused chat appear as `3 questions · ⇧←` in the left status bar.
- `Shift+Left` opens the inbox from composer insert/normal mode or transcript focus. `/questions` is the fallback.
- Choose an option with arrows, `j`/`k`, or `Ctrl+N`/`Ctrl+P`; Enter submits. `Other…` opens a separate custom-answer editor. `Ctrl+B` returns to choices.
- In the answer editor, `Shift+Enter` and `Ctrl+J` insert a newline.
- `Tab`/`Shift+Tab` move between questions and retain unfinished answer drafts. `PageUp`/`PageDown` scroll long question/context text.
- Escape or `Ctrl+C` closes the inbox and leaves questions pending. `Ctrl+D`, then Enter, explicitly declines a question; Escape cancels the decline.
- Answers go directly to the originating session, without modifying the chat composer, its caret, attachments, or Vim mode.
- Questions and answer drafts persist across restart and profile reload. Transactional claims prevent concurrent duplicate submissions.
- A send interrupted by a process crash is marked in progress/uncertain, not automatically retried.
- See [`../../CLARIFY.md`](../../CLARIFY.md) for the model contract, storage, and focused checks.

### Panel and region navigation

- `Tab` toggles between the prompt bar and message history in the active panel.
- `Ctrl+H` and `Ctrl+L` move to the panel on the left or right.
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
python3 ~/.config/yuke/tests/check-ctrl-c.py
python3 ~/.config/yuke/tests/check-composer-newlines.py
python3 ~/.config/yuke/tests/check-panel-navigation.py
python3 ~/.config/yuke/tests/check-prompt-history.py
python3 ~/.config/yuke/tests/check-sessions-reworked.py
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
