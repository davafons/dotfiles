# yuke-clarify

A background clarification inbox for this Yuke profile. The model queues a
question with `ask_question` or a batch with `request_user_input`. Both tools
return immediately, without opening a popup or stealing focus. Pending questions appear as a numbered, framed stack
**above the chat prompt**, alongside `3 questions · ⇧←` in the status bar:

```text
╭─ Questions waiting for response · Click / Shift+Left / Ctrl+H
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

Click any row in the questions banner above the prompt to open the inbox.
You can also press **Shift+Left** or **Ctrl+H** from composer insert/normal mode
or from the transcript. `/questions` and the command palette's clarification
command open the same inbox. Ctrl+H takes priority over left-panel navigation only when the
focused chat has unresolved questions; otherwise navigation is unchanged.
Modal dialogs keep control of their keys.

Ctrl+H requires the terminal's modified-key protocol, as used by the configured
Ghostty/tmux setup. Legacy terminals that send it as Backspace cannot distinguish
those keys; Backspace remains an edit. Use Shift+Left or `/questions` there.
The inbox belongs to the focused chat. Its editor is separate from the chat
composer: opening, answering, and closing it preserve the unsent chat text,
attachments, caret, and Vim mode.

| Key | Action |
| --- | --- |
| Up/Down, j/k | Move the option cursor. |
| 1–9 | Choose a single option, or toggle a multi-select checkbox. |
| Space | Toggle the current multi-select checkbox. |
| Backspace / Delete | Clear multi-select checkboxes while focused on choices. |
| Enter | Submit a standalone answer; stage a batch answer and advance to the next question or review. |
| Other… then Enter | Edit a custom answer. Multi-select can combine it with checked options. |
| Ctrl+E | Add notes alongside the chosen options. Typing from choices also opens notes. |
| Shift+Enter, Ctrl+J | Insert a newline in the answer or notes editor. |
| Ctrl+B | Return from the editor to the choices. |
| Tab / Shift+Tab | In standalone questions, next / previous question. In a batch, Tab switches between choices and notes. |
| Ctrl+P / Ctrl+N | In a batch, previous / next question; otherwise move the option cursor. |
| Left / Right | In batch choices, previous / next question. In the editor, move the caret. |
| PageUp / PageDown | Scroll long question text, context, or review. |
| Ctrl+D | Start an explicit decline or batch skip. Enter confirms; Esc cancels. |
| Esc / Ctrl+C | Close and answer later. In review, return to the question; in a confirmation, cancel it. |

Recommendations are labels, not approvals. Multi-select starts with every box
unchecked. Only an explicit answer submission authorizes delivery. A standalone
multi-select needs at least one option or a custom answer. A checked Other option
requires custom text.

Clicking a single-choice option selects it. Clicking a checkbox toggles it.
Enter still confirms the answer. Checked options have visible `[x]` marks and
accent-colored labels; the cursor row has a solid accent background with
contrasting text across its label and description. Dedicated `Clarify*`
highlight groups follow the current theme and accept theme overrides.

The picker numbers questions and response choices (`1)`, `2)`, `3)`). Its height
fits the question, context, and response rows. Text editors grow with their
content. Small terminals cap the window and scroll choices or context as needed.

### Batch review

A batch contains one to three related questions. Each question keeps its choices,
checkboxes, notes, and staged answer when navigating or closing the inbox. The
prompt stack marks staged answers `[ready]`; they have not been sent yet.

Enter on the last question opens review. Number keys 1–3 reopen questions for
editing. Enter on review submits all answers as **one user input**. An unanswered
question triggers a separate confirmation before submission. Confirmed
unanswered questions and explicit skips have empty answer arrays, never a
recommended default. The agent is told that empty answers are not approval.

## Model contract

`ask_question` queues one decision. It accepts a title (120 characters), question
(4,000), optional context (4,000), and up to eight options. An option has a label
(120), optional description (500), and optional `recommended` flag. At most one
option may be recommended. `multi_select: true` enables checkboxes and requires
options; the default is single-choice. Omit options for a free-text question.
Answers and notes have an 8,000-character combined limit.

`request_user_input` queues a related batch. Each question has a unique
snake_case `id` (64 characters), a short `header` (12), and a `question` (4,000).
Optional `context`, `options`, and `multi_select` have the same meaning as above.
The UI adds Other automatically. Recommendation labels ending in `(Recommended)`
also work and become a recommendation badge.

```json
{
  "questions": [
    {
      "id": "telemetry",
      "header": "Telemetry",
      "question": "Which telemetry should we add?",
      "multi_select": true,
      "options": [
        { "label": "Logging", "description": "Debug production problems", "recommended": true },
        { "label": "Metrics", "description": "Track service health" },
        { "label": "Tracing", "description": "Follow requests across services" }
      ]
    },
    {
      "id": "target",
      "header": "Target",
      "question": "Where should this run?",
      "options": [
        { "label": "Local (Recommended)", "description": "No remote deployment" },
        { "label": "Server", "description": "Shared access" }
      ]
    }
  ]
}
```

Both tools work in the TUI, `yuke -p`, and RPC modes. Answering requires the TUI.
Model prose is not scraped for questions. Identical unresolved single questions
or batches in the same chat reuse their pending ID. Retries of the same tool site
reuse the record, including a previously resolved answer.

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
blocked. Batch input also includes a Codex-shaped answer map keyed by the
stable question IDs. Selections remain separate strings; notes and custom text
use the `user_note:` prefix:

```json
{
  "answers": {
    "telemetry": { "answers": ["Logging", "Metrics", "user_note: Production only"] },
    "target": { "answers": ["Server"] }
  }
}
```

The question-group schema and notes flow use these Codex references:
[tool schema](https://github.com/openai/codex/blob/806d9732c974bc8a51b8317c1bd8985544fe627c/codex-rs/core/src/tools/handlers/request_user_input_spec.rs)
and [terminal question flow](https://github.com/openai/codex/blob/806d9732c974bc8a51b8317c1bd8985544fe627c/codex-rs/tui/src/bottom_pane/request_user_input/mod.rs).
This plugin keeps its original background-inbox behavior. It does not use
blocking popups or automatic timeout answers.

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
Old single-question records remain compatible; adding batch storage does not
replace or clear the existing inbox.

SQLite transactions reserve a question or an entire batch before sending.
Two Yuke instances cannot simultaneously submit the same request. Repeated Enter
during delivery is ignored. A refused engine input leaves the question pending
so the user can retry.

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
plugin and SQLite, but mocked engine answer delivery. They verify banner clicks,
clicks outside the banner, draft/caret preservation, choice and custom answers,
navigation, retry, decline, restart,
reload, transcript/insert/normal shortcuts, the slash fallback, the empty
inbox, numbered stacks above the prompt, coexistence with existing strip rows,
content-fit window heights, context scrolling, and actual ANSI selection colors.
Multi-select checks cover toggle-on/off, reload persistence, custom answers plus
checked options, and notes. Batch checks cover navigation, staging without
delivery, review edits, unanswered confirmation, retry, one combined input,
stable answer IDs, and competing process claims.
Captures are saved to a temporary text artifact and sessions are cleaned up.
No desktop app is activated, no desktop keys are sent, and the clipboard is
not accessed.
