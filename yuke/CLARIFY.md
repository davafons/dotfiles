# yuke-clarify

A background clarification inbox for this Yuke profile. The model queues a
question with `ask_question`; the tool returns immediately, without opening a
popup or stealing focus. Pending questions appear as a numbered, framed stack
**above the chat prompt**, alongside `3 questions · ⇧←` in the status bar:

```text
╭─ Questions waiting for response · Shift+Left
│  1) Deployment target — Where should this run?
│  2) Project name — What should we call it?
│  3) Storage — Which database should we use?
╰─ Answer when ready; Esc leaves questions pending
─────────────────────────────────────────────────
› Your unsent draft
```

The stack preserves Yuke's queued-input and working-prompt rows. Long summaries
are clipped with an ellipsis; large backlogs show a `+N more` row rather than
crowding out the transcript. Open the inbox for the full questions.

## Open and answer

Press **Shift+Left** from composer insert/normal mode or from the transcript.
`/questions` and the command palette's clarification command open the same inbox.
The inbox belongs to the focused chat. Its editor is separate from the chat
composer: opening, answering, and closing it preserve the unsent chat text,
attachments, caret, and Vim mode.

| Key | Action |
| --- | --- |
| Up/Down, j/k, Ctrl+N/P | Move between single-choice options. |
| Enter | Submit the selected choice or typed answer. |
| Other… then Enter | Write a custom answer instead of a listed choice. |
| Shift+Enter, Ctrl+J | Insert a newline in a typed answer. |
| Ctrl+B | Return from a custom answer to the choices. |
| Tab / Shift+Tab | Next / previous question, retaining unfinished answers. |
| PageUp / PageDown | Scroll long question text and context. |
| Ctrl+D | Start an explicit decline; Enter confirms, Esc cancels. |
| Esc / Ctrl+C | Close and answer later. Nothing is answered or declined. |

Recommendations are labels, not approvals. No answer is submitted just by opening
the inbox. An accepted answer advances to the next question; the final answer
closes the inbox. Clicking an option selects it; Enter still submits.

The picker numbers both questions and response choices (`1)`, `2)`, `3)`). It
sizes itself to the question, context, and response rows instead of taking a
fixed percentage of the screen; free-text editors grow with their content. A
small terminal caps the window and scrolls the choices or context as needed.
Question headings, subdued context/descriptions, recommendation badges, and
selected-row backgrounds use dedicated `Clarify*` highlight groups and the
current theme's palette. Theme overrides remain possible.

## Model contract

`ask_question` accepts a title (120 characters), question (4,000), optional context
(4,000), and up to eight single-choice options. An option has a label (120),
optional description (500), and optional `recommended` flag. At most one option
may be recommended. Omit options for a free-text question. Users may always choose
a custom answer, up to 8,000 characters.

The tool works in the TUI, `yuke -p`, and RPC modes. Answering requires the TUI:
resume the originating chat there. Model prose is not automatically scraped for
questions. Identical pending questions in the same chat and retries of the same
tool site reuse their question ID.

The prompt instructs the agent to continue **independent work only** after asking.
It must not guess an answer or act on a decision that still needs clarification.
This is an instruction to the model, not a tool-execution sandbox.

Answers are sent as user inputs directly to the **originating session**, never
through the current composer. Yuke starts a run or queues the answer while that
session is working. Each input includes the question ID, question text, context,
and either the user's answer or an explicit decline:

```text
[yuke-clarify q-…: answered]

Title: Deployment target

Question: Where should this run?

User answer: Local
```

The original tool call and subsequent answer remain visible in the transcript.
Declines explicitly say they are not approval and that dependent work stays
blocked.

## Persistence and delivery safety

Python 3 with its standard-library SQLite support is required. The inbox lives
outside the repository at:

```text
${XDG_STATE_HOME:-~/.local/state}/${YUKE_APPNAME:-yuke}/clarify/questions.sqlite3
```

New inbox directories are private (`0700`), and the database is `0600`. Question
records, unfinished answer drafts, and completed delivery receipts survive
restarts and `/reload`. The database retains completed records, but this initial
UI lists only unresolved questions; history and an all-chats inbox are not yet
implemented. Drafts save after a short debounce and when switching or closing.

SQLite transactions reserve a question before sending, so two Yuke instances
cannot simultaneously submit it. Repeated Enter during delivery is ignored. A
refused engine input leaves the question pending so the user can retry.

**Crash boundary:** the engine and inbox database do not share a transaction. If
Yuke dies after reserving a send, or an accepted input's receipt cannot be saved,
the record stays `sending` and the inbox reports delivery as in progress or
uncertain. It deliberately does not resend: check the originating transcript
before attempting manual recovery. Automatic crash recovery is not implemented.

## Install and verify

The profile registers `yukeClarify` from `plugins/yuke-clarify.js`. Its companion
`plugins/yuke-clarify-store.py` must also be installed. This checkout's live
profile links have been installed. Use the custom **`/reload`** to activate the
change, or restart Yuke. The stable `index.js` loader was not changed.

From the repository root:

```sh
node yuke/.config/yuke/tests/check-yuke-clarify.mjs
python3 yuke/.config/yuke/tests/check-yuke-clarify-store.py
python3 yuke/.config/yuke/tests/check-yuke-clarify-tui.py
npx --yes --package typescript tsc -p ~/.config/yuke/jsconfig.json
yuke check
```

The tool checks exercise validation and real persistence without a provider. The
store checks include two competing processes, owner-token checks, duplicate
questions, draft persistence, and private file modes. The TUI checks use a
unique detached tmux window and temporary XDG directories: real keys, the real
plugin and SQLite, but mocked engine answer delivery. They verify draft/caret
preservation, choice and custom answers, navigation, retry, decline, restart,
reload, transcript/insert/normal shortcuts, the slash fallback, the empty
inbox, numbered stacks above the prompt, coexistence with existing strip rows,
content-fit window heights, context scrolling, and actual ANSI selection colors.
Captures are saved to a temporary text artifact and sessions are cleaned up. No desktop app is activated, no desktop keys are sent, and the clipboard is
not accessed.
