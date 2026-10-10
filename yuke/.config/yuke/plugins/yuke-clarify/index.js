//! A quiet, persistent clarification inbox. Never borrows the chat composer.
import { client, env, events, exec } from "yuke";
import { currentSession } from "yuke:session";
import { clip, Composer, List, Pager, Window } from "yuke:ui";
import { wrapRows } from "yuke:chat";

/** @import { Rect } from "yuke:ui" */
/** @typedef {NonNullable<NonNullable<ConstructorParameters<typeof Window>[0]>["content"]>} WindowContent */
/** @typedef {{ label: string, description: string, recommended: boolean }} Choice */
/** @typedef {{ title: string, question: string, context: string, options: Choice[], multi_select: boolean }} Question */
/** @typedef {{ text: string, selected: number, other: boolean, checked?: number[], otherSelected?: boolean, notes?: boolean, committed?: boolean, responses?: string[] }} Draft */
/** @typedef {Question & { id: string, session: string, status: string, draft: Draft, token?: string, answer?: string, kind?: string, error?: string, responses?: string[], question_id?: string, batch_id?: string, batch_size?: number, batch_index?: number }} Entry */
/** @typedef {{ id: string, session: string, status: string, questions: Entry[], answers?: Record<string, { answers: string[] }>, token?: string }} Batch */

/** @param {unknown} value @param {string} name @param {number} max */
function requiredText(value, name, max) {
  if (typeof value !== "string" || !value.trim() || value.length > max || /[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/u.test(value)) {
    throw new Error(`${name} must be nonempty text of at most ${max} characters without control codes`);
  }
  return value.trim();
}

/** Validate model arguments before persisting anything. @param {unknown} args @returns {Question} */
export function validateQuestion(args) {
  if (!args || typeof args !== "object" || Array.isArray(args)) throw new Error("question arguments must be an object");
  const value = /** @type {Record<string, unknown>} */ (args);
  if (Object.keys(value).some((key) => !["title", "question", "context", "options", "multi_select"].includes(key))) throw new Error("unknown question field");
  if (value.multi_select !== undefined && typeof value.multi_select !== "boolean") throw new Error("multi_select must be boolean");
  const title = requiredText(value.title, "title", 120);
  const question = requiredText(value.question, "question", 4000);
  const context = value.context === undefined || value.context === "" ? "" : requiredText(value.context, "context", 4000);
  if (value.options !== undefined && (!Array.isArray(value.options) || value.options.length > 8)) throw new Error("options must be an array of at most 8 choices");
  const options = (/** @type {unknown[]} */ (value.options ?? [])).map((option) => {
    if (!option || typeof option !== "object" || Array.isArray(option)) throw new Error("each option must be an object");
    const choice = /** @type {Record<string, unknown>} */ (option);
    if (Object.keys(choice).some((key) => !["label", "description", "recommended"].includes(key))) throw new Error("unknown option field");
    if (choice.recommended !== undefined && typeof choice.recommended !== "boolean") throw new Error("recommended must be boolean");
    return {
      label: requiredText(choice.label, "option label", 120),
      description: choice.description === undefined || choice.description === "" ? "" : requiredText(choice.description, "option description", 500),
      recommended: choice.recommended === true,
    };
  });
  if (new Set(options.map((choice) => choice.label)).size !== options.length) throw new Error("option labels must be unique");
  if (options.filter((choice) => choice.recommended).length > 1) throw new Error("only one option can be recommended");
  if (value.multi_select === true && !options.length) throw new Error("multi_select requires options");
  return { title, question, context, options, multi_select: value.multi_select === true };
}

/** @param {unknown} args @returns {(Question & { question_id: string })[]} */
export function validateBatch(args) {
  if (!args || typeof args !== "object" || Array.isArray(args)) throw new Error("batch arguments must be an object");
  const value = /** @type {Record<string, unknown>} */ (args);
  if (Object.keys(value).some((key) => key !== "questions")) throw new Error("unknown batch field");
  if (!Array.isArray(value.questions) || value.questions.length < 1 || value.questions.length > 3) throw new Error("provide one to three questions");
  const questions = value.questions.map((raw) => {
    if (!raw || typeof raw !== "object" || Array.isArray(raw)) throw new Error("each question must be an object");
    const item = /** @type {Record<string, unknown>} */ (raw);
    if (Object.keys(item).some((key) => !["id", "header", "question", "context", "options", "multi_select"].includes(key))) throw new Error("unknown batch question field");
    const id = requiredText(item.id, "question id", 64);
    if (!/^[a-z][a-z0-9_]*$/u.test(id)) throw new Error("question ids must be snake_case");
    const header = requiredText(item.header, "header", 12);
    const options = Array.isArray(item.options) ? item.options.map((option) => {
      if (!option || typeof option !== "object" || Array.isArray(option)) return option;
      const choice = /** @type {Record<string, unknown>} */ (option);
      const label = typeof choice.label === "string" ? choice.label : "";
      return /\s*\(recommended\)$/iu.test(label)
        ? { ...choice, label: label.replace(/\s*\(recommended\)$/iu, ""), recommended: true } : choice;
    }) : item.options;
    return { ...validateQuestion({ title: header, question: item.question,
      ...(item.context !== undefined ? { context: item.context } : {}),
      ...(options !== undefined ? { options } : {}),
      ...(item.multi_select !== undefined ? { multi_select: item.multi_select } : {}),
    }), question_id: id };
  });
  if (new Set(questions.map((question) => question.question_id)).size !== questions.length) throw new Error("question ids must be unique");
  return questions;
}

/** @param {Entry} entry @param {Draft} draft */
export function questionResponse(entry, draft) {
  const checked = [...new Set(draft.checked ?? [])].filter((index) => Number.isInteger(index) && index >= 0 && index < entry.options.length).sort((a, b) => a - b);
  const custom = draft.otherSelected ?? draft.other;
  const labels = entry.multi_select ? checked.map((index) => entry.options[index].label)
    : entry.options.length && !custom ? [entry.options[Math.min(draft.selected, entry.options.length - 1)].label] : [];
  const text = draft.text.trim();
  const note = text && (custom || draft.notes || !entry.options.length) ? text : "";
  const responses = [...labels, ...(note ? [entry.batch_id || labels.length ? `user_note: ${note}` : note] : [])];
  return { responses, text: [...labels, ...(note ? [note] : [])].join("\n") };
}

/** @param {Batch} batch */
export function batchAnswerMessage(batch) {
  const summary = batch.questions.map((question) => [
    `${question.question_id}: ${question.question}`,
    ...(question.context ? [`Context: ${question.context}`] : []),
    (batch.answers?.[question.question_id ?? question.id]?.answers ?? []).join("; ") || "Unanswered / skipped (not approval)",
  ].join("\n")).join("\n\n");
  return `[yuke-clarify ${batch.id}: answered]\n\n${summary}\n\nStructured answers:\n${JSON.stringify({ answers: batch.answers })}\n\nEmpty answer arrays are unanswered or explicitly skipped, NOT approval. Leave work dependent on those unanswered questions blocked.`;
}

/** The answer is user-authored content, with an unambiguous correlation ID. @param {Entry} entry */
export function answerMessage(entry) {
  return [
    `[yuke-clarify ${entry.id}: ${entry.kind}]`,
    `Title: ${entry.title}`,
    `Question: ${entry.question}`,
    ...(entry.context ? [`Context: ${entry.context}`] : []),
    entry.kind === "dismissed"
      ? "The user declined to answer. Do not treat this as approval or choose a default. Leave dependent work blocked."
      : `User answer: ${entry.answer}`,
    ...(entry.responses?.length ? [`Structured answers: ${JSON.stringify({ answers: entry.responses })}`] : []),
  ].join("\n\n");
}

/** @param {string} value */
function quote(value) { return "'" + value.replaceAll("'", "'\\''") + "'"; }
/** Register the migrated yuke-clarify operations. The plugin owns registrations; host failures throw. @param {import("yuke").Context} parent */
export default function(parent) {

    const home = env.get("HOME") || ".";
    const app = env.get("YUKE_APPNAME") || "yuke";
    const config = (env.get("XDG_CONFIG_HOME") || home + "/.config") + "/" + app;
    const database = (env.get("XDG_STATE_HOME") || home + "/.local/state") + "/" + app + "/clarify/questions.sqlite3";
    /** @type {Entry[]} */
    let entries = [];
    let unavailable = false;
    let repaint = () => {};
    let tail = Promise.resolve();

    /** Serialize local operations; SQLite also arbitrates between processes. @param {string} action @param {Record<string, unknown>} [args] */
    function store(action, args = {}) {
      const result = tail.then(async () => {
        const command = ["python3", config + "/plugins/yuke-clarify-store.py", database, action, JSON.stringify(args)].map(quote).join(" ");
        const output = await exec(command);
        if (output.code !== 0) throw new Error((output.stderr || output.stdout || "clarification storage failed").trim());
        return JSON.parse(output.stdout);
      });
      tail = result.then(() => {}, () => {});
      return result;
    }

    async function refresh() {
      try {
        entries = await store("list");
        unavailable = false;
      } catch (error) {
        if (!unavailable && parent.alive) parent.interaction.notify("Questions unavailable: " + String(error), "error");
        unavailable = true;
      }
      if (parent.alive) repaint();
    }
    let initialized = false;
    const initialRefresh = refresh().finally(() => { initialized = true; });
    // Refresh other instances' changes, but never poll from a render callback.
    let polling = false;
    const timer = setInterval(() => {
      if (polling) return;
      polling = true;
      void refresh().finally(() => { polling = false; });
    }, 2000);
    parent.own(() => clearInterval(timer));
    parent.own(() => tail);

    parent.hook("prompt.build", (payload) => ({ replace: { sections: [...payload.sections, {
      key: "yuke-clarify",
      text: "Use ask_question for one decision or request_user_input for a related batch of one to three questions. Set multi_select only when several options may be chosen. Both tools queue immediately, without approval. Use these tools for decisions that require user clarification. It queues a question and returns immediately; it is not an answer or approval. Continue only independent work, never guess an answer or perform dependent actions. If blocked, explain what is waiting and end your turn. Do not repeatedly ask the same pending question. Answers arrive later as user messages marked [yuke-clarify <id>: answered] or dismissed. In the TUI the user opens questions with Shift+Left, Ctrl+H, or /questions. In headless mode tell them to resume this chat in the TUI to answer.",
    }] } }));

    parent.tools.define({
      name: "ask_question",
      description: "Queue one clarification for the user without opening a popup or waiting for an answer. Supply a short title, question, optional context, and up to 8 options (at most one recommended). Set multi_select:true for checkbox-style multiple selections; omit options for free text. The user can always give a custom answer. The result is only a pending-question ID, NOT approval. Continue independent work only; stop dependent work until the user answers. Do not duplicate a pending question.",
      parameters: {
        type: "object", additionalProperties: false,
        properties: {
          title: { type: "string", maxLength: 120, description: "Short inbox title." },
          question: { type: "string", maxLength: 4000, description: "The decision the user must clarify." },
          context: { type: "string", maxLength: 4000, description: "Why the answer matters." },
          multi_select: { type: "boolean", description: "Allow several options to be selected together; defaults to false." },
          options: { type: "array", maxItems: 8, items: {
            type: "object", additionalProperties: false,
            properties: {
              label: { type: "string", maxLength: 120 },
              description: { type: "string", maxLength: 500 },
              recommended: { type: "boolean" },
            }, required: ["label"],
          } },
        }, required: ["title", "question"],
      },
      async execute(args, signal, toolCtx) {
        const question = validateQuestion(args);
        if (signal.aborted || !parent.alive) throw new Error("question canceled before queueing");
        const entry = /** @type {Entry} */ (await store("add", {
          question, session: toolCtx.sessionId,
          site: `${toolCtx.sessionId}:${toolCtx.messageId}:${toolCtx.partId}`,
        }));
        await refresh();
        const message = entry.status === "pending"
          ? "Queued, not answered. Continue independent work only. The user can answer with Shift+Left, Ctrl+H, or /questions in this chat."
          : entry.status === "sending"
            ? "An answer delivery is in progress or uncertain. Do not ask again or assume approval."
            : "This tool call has already been resolved. Read the recorded answer or decline; do not queue it again.";
        return JSON.stringify({ id: entry.id, status: entry.status, message, ...(entry.answer ? { answer: entry.answer } : {}) });
      },
    });

    parent.tools.define({
      name: "request_user_input",
      description: "Queue a related batch of one to three clarification questions, with short headers and stable snake_case IDs. The user can select a choice, select several when multi_select:true, add notes or a custom answer, review, and submit the batch together. This returns immediately with a PENDING request ID, not answers or approval. Continue independent work only and stop dependent work until the user responds. Do not include an Other option; the UI adds it.",
      parameters: {
        type: "object", additionalProperties: false, required: ["questions"], properties: {
          questions: { type: "array", minItems: 1, maxItems: 3, items: {
            type: "object", additionalProperties: false, required: ["id", "header", "question"], properties: {
              id: { type: "string", pattern: "^[a-z][a-z0-9_]*$", maxLength: 64 },
              header: { type: "string", maxLength: 12 },
              question: { type: "string", maxLength: 4000 },
              context: { type: "string", maxLength: 4000 },
              multi_select: { type: "boolean" },
              options: { type: "array", maxItems: 8, items: {
                type: "object", additionalProperties: false, required: ["label"], properties: {
                  label: { type: "string", maxLength: 120 }, description: { type: "string", maxLength: 500 }, recommended: { type: "boolean" },
                },
              } },
            },
          } },
        },
      },
      async execute(args, signal, toolCtx) {
        const questions = validateBatch(args);
        if (signal.aborted || !parent.alive) throw new Error("questions canceled before queueing");
        const batch = /** @type {Batch} */ (await store("add_batch", {
          questions, session: toolCtx.sessionId, site: `${toolCtx.sessionId}:${toolCtx.messageId}:${toolCtx.partId}`,
        }));
        await refresh();
        return JSON.stringify({ id: batch.id, status: batch.status, questions: batch.questions.map((question) => ({ id: question.question_id, pending_id: question.id })),
          message: batch.status === "pending" ? "Queued, not answered. Continue independent work only. Open with Shift+Left, Ctrl+H, or /questions; the user reviews and submits the batch together."
            : batch.status === "sending" ? "Delivery in progress or uncertain; do not assume approval or ask again." : "This request was already resolved. Read its recorded answers.",
          ...(batch.status === "answered" ? { answers: batch.answers } : {}),
        });
      },
    });

    {
const chatBorrow = parent.get("chat");
if (chatBorrow) {
const c = { ctx: parent, chat: chatBorrow };

      c.chat.render({ tools: {
        ask_question: (args) => ({ verb: "ask", subject: String(args.title || "clarification"), input: "" }),
        request_user_input: (args) => ({ verb: "ask", subject: `${Array.isArray(args.questions) ? args.questions.length : ""} clarifications`, input: "" }),
      } });
}
}

    {
const tuiBorrow = parent.get("tui");
if (tuiBorrow) {
const c = { ctx: parent, tui: tuiBorrow };

      c.tui.style.set({
        ClarifyTitle: { fg: "accent", bold: true },
        ClarifyBorder: { fg: "accent" },
        ClarifyQuestion: { fg: "strongFg", bold: true },
        ClarifyContext: { link: "UIDim" },
        ClarifyChoice: { fg: "surfaceFg" },
        ClarifyChecked: { fg: "accent", bold: true },
        ClarifyRecommended: { fg: "warn", bold: true },
        ClarifySelected: { fg: "bg", bg: "accent", bold: true },
        ClarifySelectedDetail: { fg: "bg", bg: "accent" },
        ClarifySelectedBadge: { fg: "bg", bg: "accent", bold: true },
        ClarifyWarning: { fg: "warn", bold: true },
        ClarifyError: { fg: "danger", bold: true },
      }, { default: true });
      repaint = () => c.tui.root.invalidate();
      c.ctx.own(() => { repaint = () => {}; });
      c.tui.status.add({ side: "left", order: 45, render: () => {
        if (unavailable) return "questions unavailable";
        const count = entries.filter((entry) => entry.session === currentSession()?.sessionId).length;
        return count ? `${count} question${count === 1 ? "" : "s"} · ⇧←` : "";
      } });
      // chat.strip is a bail event: a plain listener would replace queued-input
      // and working-prompt rows. Append to the existing answer instead.
      c.ctx.advise(events, "bail", "around", (next, name, ...args) => {
        const rows = next(name, ...args);
        if (name !== "chat.strip") return rows;
        const view = /** @type {import("yuke:chat").ChatView} */ (args[0]);
        const waiting = entries.filter((item) => item.session === view.session.sessionId);
        if (!waiting.length) return rows;
        const limit = Math.max(1, Math.floor(view.rect.h / 3) - 2);
        const shown = waiting.slice(0, limit);
        const stack = [
          { text: "╭─ Questions waiting for response · Click / Shift+Left / Ctrl+H", group: "ClarifyTitle" },
          ...shown.map((item, number) => ({
            text: clip(`│  ${number + 1}) ${item.title}${item.draft.committed ? " [ready]" : ""} — ${item.question.replace(/\s+/gu, " ")}${item.status === "sending" ? " [delivery pending]" : ""}`, view.rect.w, true),
            group: item.status === "sending" ? "ClarifyWarning" : "ClarifyQuestion",
          })),
          ...(waiting.length > shown.length ? [{ text: `│  +${waiting.length - shown.length} more · /questions`, group: "ClarifyContext" }] : []),
          { text: "╰─ Answer when ready; Esc leaves questions pending", group: "ClarifyContext" },
        ];
        return [...(Array.isArray(rows) ? rows : []), ...stack];
      });
      c.ctx.on("chat.press", (view, ev) => {
        const rect = view.stripRect;
        const row = ev.row - rect.y;
        if (ev.col < rect.x || ev.col >= rect.x + rect.w || row < 0 || row >= rect.h ||
            !view.strip[row]?.group?.startsWith("Clarify")) return;
        c.tui.command.perform("yuke-clarify:questions");
        return true;
      });
      let opened = false;

      async function openInbox() {
        if (opened) return;
        opened = true;
        await refresh();
        const sessionId = currentSession()?.sessionId;
        const pending = entries.filter((entry) => entry.session === sessionId);
        if (!c.ctx.alive || unavailable || pending.length === 0) {
          opened = false;
          if (c.ctx.alive && !unavailable) c.ctx.interaction.notify("No pending questions in this chat.");
          return;
        }
        let index = 0;
        let entry = pending[index];
        let busy = false;
        let confirmingDismiss = false;
        let notice = "";
        let saving = false;
        /** @type {Set<number>} */
        let checked = new Set();
        let otherSelected = false;
        let notes = false;
        let committed = false;
        /** @type {string[]} */
        let responses = [];
        let review = false;
        let confirmingUnanswered = false;
        /** @type {number | undefined} */
        let saveTimer;
        /** @type {() => void} */
        let close = () => {};
        const heading = new Pager();
        let headingText = "";
        let headingWidth = 0;
        /** @type {Rect | null} */
        let headingRect = null;
        let headingRows = 0;
        const answer = new Composer({ placeholder: "Type your answer" });
        answer.maxRows = 5;
        /** @type {List<Choice>} */
        const choices = new List({
          items: /** @type {Choice[]} */ ([]), itemHeight: 2,
          group: "ClarifyChoice", selGroup: "ClarifySelected",
          dimGroup: "ClarifyContext", dimSelGroup: "ClarifySelectedDetail",
          format: (choice, number) => ({ lines: [
            { text: `${entry.multi_select ? ((number === entry.options.length ? otherSelected : checked.has(number)) ? "[x] " : "[ ] ") : ""}${number + 1}) ${choice.label}`, indent: 2,
              group: entry.multi_select && (number === entry.options.length ? otherSelected : checked.has(number)) ? "ClarifyChecked" : "ClarifyChoice",
              marker: !editing && choices.selectedIndex() === number ? "›" : " ",
              markerGroup: "ClarifyTitle", markerSelGroup: "ClarifySelected",
              right: choice.recommended ? "recommended" : "",
              rightGroup: "ClarifyRecommended", rightSelGroup: "ClarifySelectedBadge" },
            { text: choice.description, indent: 5, group: "ClarifyContext", selGroup: "ClarifySelectedDetail" },
          ] }),
        });
        let editing = false;
        /** @type {Rect | null} */
        let choiceRect = null;

        function draft() {
          if (review) return entry.draft;
          return { text: answer.text, selected: Math.max(0, choices.selectedIndex()), other: editing && entry.options.length > 0,
            checked: [...checked].sort((a, b) => a - b), otherSelected, notes, committed, responses };
        }
        async function saveDraft() {
          clearTimeout(saveTimer);
          if (entry.status !== "pending") return false;
          const id = entry.id;
          const value = draft();
          entry.draft = value;
          try { await store("draft", { id, draft: value }); return true; }
          catch (error) { if (c.ctx.alive) c.ctx.interaction.notify("Could not save answer draft: " + String(error), "error"); return false; }
        }
        function changed() {
          if (saving) return;
          committed = false;
          responses = [];
          clearTimeout(saveTimer);
          saveTimer = setTimeout(() => { void saveDraft(); }, 250);
          repaint();
        }
        const invalidateAnswer = answer.input.onChange;
        answer.input.onChange = () => { invalidateAnswer?.(); changed(); };
        choices.onMove = () => {
          if (!saving && !entry.multi_select) {
            otherSelected = choices.selectedIndex() === entry.options.length;
            if (otherSelected) notes = false;
          }
          changed();
        };

        function load() {
          saving = true;
          notice = entry.error ? "Previous delivery failed; you may retry." : "";
          confirmingDismiss = false;
          confirmingUnanswered = false;
          review = false;
          heading.toTop();
          checked = new Set(entry.draft.checked ?? []);
          otherSelected = entry.draft.otherSelected ?? entry.draft.other;
          notes = entry.draft.notes ?? false;
          committed = entry.draft.committed ?? false;
          responses = entry.draft.responses ?? [];
          answer.text = entry.draft.text;
          editing = entry.options.length === 0 || entry.draft.other;
          choices.itemHeight = entry.options.some((choice) => choice.description) ? 2 : 1;
          choices.setItems([...entry.options, { label: "Other…", description: "Write a custom answer", recommended: false }]);
          choices.navEdge(-1);
          choices.navBy(Math.min(entry.draft.selected, entry.options.length));
          saving = false;
          repaint();
        }
        /** @param {number} direction @param {boolean} [withinBatch] */
        async function navigate(direction, withinBatch = false) {
          if (busy) return;
          busy = true;
          await saveDraft();
          const indices = withinBatch && entry.batch_id
            ? pending.flatMap((item, position) => item.batch_id === entry.batch_id ? [position] : [])
            : pending.map((_, position) => position);
          index = indices[(indices.indexOf(index) + direction + indices.length) % indices.length];
          entry = pending[index];
          load();
          busy = false;
        }

        /** Claim before sending; no retry after an accepted input whose receipt failed to save. @param {"answered" | "dismissed"} kind */
        async function deliver(kind) {
          if (busy || entry.status !== "pending") return;
          const response = questionResponse(entry, draft());
          const text = response.text;
          if (kind === "answered" && ((!text && !entry.batch_id) || text.length > 8000)) {
            notice = entry.multi_select && !text ? "Select at least one option, or choose Other…" : "Enter an answer (at most 8000 characters)."; repaint(); return;
          }
          if (entry.batch_id) {
            busy = true;
            responses = kind === "dismissed" ? [] : response.responses;
            committed = kind === "dismissed" || responses.length > 0;
            if (!await saveDraft()) { busy = false; notice = "Could not save this answer. Please retry."; repaint(); return; }
            const nextIndex = pending.findIndex((item) => item.batch_id === entry.batch_id && item.batch_index === (entry.batch_index ?? 0) + 1);
            if (nextIndex >= 0) { index = nextIndex; entry = pending[index]; load(); }
            else { review = true; confirmingDismiss = false; notice = ""; heading.toTop(); }
            busy = false;
            repaint();
            return;
          }
          busy = true;
          await saveDraft();
          if (!c.ctx.alive) { busy = false; return; }
          notice = "Sending answer…";
          repaint();
          /** @type {Entry | undefined} */
          let claim;
          let accepted = false;
          try {
            claim = /** @type {Entry} */ (await store("claim", { id: entry.id, kind, answer: kind === "dismissed" ? "" : text, responses: kind === "dismissed" ? [] : response.responses }));
            const result = await client.sessionSendInput(claim.session, client.textContent(answerMessage(claim)));
            accepted = true;
            await store("finish", { id: claim.id, token: claim.token, input_id: result.input_id });
            pending.splice(index, 1);
            await refresh();
            if (pending.length === 0) { close(); return; }
            index %= pending.length;
            entry = pending[index];
            load();
          } catch (error) {
            if (claim && !accepted) {
              try { await store("release", { id: claim.id, token: claim.token, error: String(error) }); }
              catch { entry.status = "sending"; }
            } else if (claim) entry.status = "sending";
            notice = accepted ? "Answer accepted, but its receipt could not be saved. Do not resend." : "Could not deliver: " + String(error);
            await refresh();
            // A different instance may already own or have completed the claim.
            const updated = entries.find((item) => item.id === entry.id);
            if (updated) entry.status = updated.status;
            else entry.status = "answered";
          } finally { busy = false; repaint(); }
        }

        function batchQuestions() { return pending.filter((item) => item.batch_id === entry.batch_id); }
        async function submitBatch(allowUnanswered = false) {
          if (busy || !entry.batch_id || entry.status !== "pending") return;
          if (!allowUnanswered && batchQuestions().some((item) => !item.draft.committed)) {
            confirmingUnanswered = true; repaint(); return;
          }
          busy = true;
          notice = "Submitting all answers…";
          repaint();
          /** @type {Batch | undefined} */
          let claim;
          let accepted = false;
          try {
            claim = /** @type {Batch} */ (await store("claim_batch", { id: entry.batch_id, allow_unanswered: allowUnanswered }));
            const result = await client.sessionSendInput(claim.session, client.textContent(batchAnswerMessage(claim)));
            accepted = true;
            await store("finish_batch", { id: claim.id, token: claim.token, input_id: result.input_id });
            for (let position = pending.length - 1; position >= 0; position--) if (pending[position].batch_id === claim.id) pending.splice(position, 1);
            await refresh();
            if (!pending.length) { close(); return; }
            index %= pending.length; entry = pending[index]; load();
          } catch (error) {
            if (claim && !accepted) {
              try { await store("release_batch", { id: claim.id, token: claim.token, error: String(error) }); }
              catch { entry.status = "sending"; }
            } else if (claim) entry.status = "sending";
            notice = accepted ? "Answers accepted, but the receipt could not be saved. Do not resend." : "Could not deliver: " + String(error);
            await refresh();
            const updated = entries.find((item) => item.id === entry.id);
            entry.status = updated?.status ?? "answered";
          } finally { busy = false; repaint(); }
        }
        function toggleChoice() {
          const selected = choices.selectedIndex();
          if (selected === entry.options.length) otherSelected = !otherSelected;
          else if (checked.has(selected)) checked.delete(selected);
          else checked.add(selected);
          changed();
        }
        function editNotes() {
          if (choices.selectedIndex() === entry.options.length) { otherSelected = true; notes = false; }
          else notes = true;
          editing = true;
          changed();
        }
        /** @param {number} width */
        function questionRows(width) {
          if (review) {
            const questions = batchQuestions();
            const count = questions.filter((item) => !item.draft.committed).length;
            return [
              ...wrapRows(confirmingUnanswered ? `Submit with ${count} unanswered question${count === 1 ? "" : "s"}?` : `Review answers · ${questions.length - count}/${questions.length} ready`, width, "ClarifyTitle", 0),
              { text: "", group: "ClarifyContext" },
              ...questions.flatMap((item, number) => [
                ...wrapRows(`${item.draft.committed ? "✓" : "○"} ${number + 1}) ${item.title}`, width, item.draft.committed ? "ClarifyChecked" : "ClarifyWarning", 0),
                ...wrapRows(clip(item.draft.committed ? (item.draft.responses?.join("; ") || "Explicitly skipped (not approval)") : "Unanswered (not approval)", 180, true), width, "ClarifyContext", 0),
              ]),
              ...(notice ? wrapRows(notice, width, "ClarifyWarning", 0) : []),
              ...(confirmingUnanswered ? wrapRows("Enter submits with empty answers for unanswered questions. Esc returns to review; no default is chosen.", width, "ClarifyWarning", 0) : []),
            ];
          }
          const blocks = [
            { text: `${entry.batch_id ? (entry.batch_index ?? 0) + 1 : index + 1}) ${entry.question}`, group: "ClarifyQuestion" },
            { text: entry.context, group: "ClarifyContext" },
            { text: entry.multi_select ? "Choose any that apply. Space or number keys toggle selections; Enter confirms." : "", group: "ClarifyTitle" },
            { text: notice, group: notice.startsWith("Could not") ? "ClarifyError" : "ClarifyWarning" },
            { text: entry.status !== "pending" ? "Delivery in progress or uncertain. Automatic resend is disabled." : "", group: "ClarifyWarning" },
            { text: confirmingDismiss ? "Decline this question? Enter confirms; Esc keeps it pending." : "", group: "ClarifyWarning" },
          ].filter((block) => block.text);
          return blocks.flatMap((block, number) => [
            ...(number ? [{ text: "", group: "ClarifyContext" }] : []),
            ...wrapRows(block.text, width, block.group, 0),
          ]);
        }
        function showChoices() { return entry.options.length > 0 && (!editing || notes || entry.multi_select); }
        /** @param {number} width */
        function responsesHeight(width) {
          if (review || entry.status !== "pending" || confirmingDismiss) return 0;
          const list = showChoices() ? choices.items.length * choices.itemHeight : 0;
          const editor = editing ? Math.max(1, answer.height(width)) : 0;
          return list + editor + (list && editor ? 1 : 0);
        }
        /** @type {WindowContent} */
        const content = {
          layout(rect) {
            const rows = questionRows(rect.w);
            const value = JSON.stringify(rows);
            if (value !== headingText || rect.w !== headingWidth) {
              headingRows = rows.length;
              if (!notice && !confirmingDismiss && entry.status === "pending") heading.stuck = false;
              heading.setRows(rows);
              if (notice || confirmingDismiss || entry.status !== "pending") heading.toBottom();
              headingText = value;
              headingWidth = rect.w;
            }
            const bodyHeight = responsesHeight(rect.w);
            const gap = bodyHeight ? 1 : 0;
            const headerHeight = Math.min(rect.h, headingRows, Math.max(1, rect.h - bodyHeight - gap));
            headingRect = { ...rect, h: headerHeight };
            const rest = { ...rect, y: rect.y + headerHeight + gap, h: Math.max(0, rect.h - headerHeight - gap) };
            const editorHeight = editing ? Math.min(rest.h, Math.max(1, answer.height(rest.w))) : 0;
            const listGap = showChoices() && editorHeight && rest.h > editorHeight ? 1 : 0;
            const listHeight = showChoices() ? Math.max(0, rest.h - editorHeight - listGap) : 0;
            choiceRect = { ...rest, h: listHeight };
            if (editing) answer.layout({ ...rest, y: rest.y + listHeight + listGap, h: editorHeight });
          },
          draw(focused) {
            if (headingRect) {
              if (!notice && !confirmingDismiss && entry.status === "pending") heading.stuck = false;
              heading.draw(headingRect);
            }
            if (review || entry.status !== "pending" || confirmingDismiss) return;
            choices.drawCursor = !editing;
            if (showChoices() && choiceRect) choices.draw(choiceRect);
            if (editing) answer.draw(focused);
          },
          cursor: () => !review && editing && entry.status === "pending" && !confirmingDismiss ? answer.cursor() : null,
          onKey(ev) {
            if (busy) return true;
            if (ev.type === "key" && ev.event === "release") return true;
            if (ev.type === "key") {
              const key = ev.code === "char" ? ev.char : ev.code;
              if (key === "esc" || (key === "c" && ev.mods === 4)) {
                if (confirmingUnanswered) { confirmingUnanswered = false; repaint(); }
                else if (review) { review = false; load(); }
                else if (confirmingDismiss) { confirmingDismiss = false; repaint(); }
                else close();
                return true;
              }
              if (key === "page_up" || key === "page_down") { heading.navPage(key === "page_up" ? -1 : 1); repaint(); return true; }
              if (review) {
                if (key === "enter") void submitBatch(confirmingUnanswered);
                else if (/^[1-3]$/u.test(key) && ev.mods === 0 && !confirmingUnanswered) {
                  const target = batchQuestions()[Number(key) - 1];
                  if (target) { index = pending.indexOf(target); entry = target; load(); }
                }
                return true;
              }
              if (confirmingDismiss) {
                if (key === "enter") void deliver("dismissed");
                return true;
              }
              if (entry.batch_id && ((key === "p" || key === "n") && ev.mods === 4)) { void navigate(key === "p" ? -1 : 1, true); return true; }
              if (entry.batch_id && !editing && (key === "left" || key === "right") && ev.mods === 0) { void navigate(key === "left" ? -1 : 1, true); return true; }
              if (key === "tab") {
                if (entry.status !== "pending") { void navigate(ev.mods === 1 ? -1 : 1); return true; }
                if (entry.batch_id && entry.options.length) { if (editing) { editing = false; changed(); } else editNotes(); }
                else void navigate(ev.mods === 1 ? -1 : 1);
                return true;
              }
              if (entry.status !== "pending") return true;
              if (key === "d" && ev.mods === 4) { confirmingDismiss = true; repaint(); return true; }
              if (key === "b" && ev.mods === 4 && entry.options.length) { editing = false; changed(); return true; }
              if (key === "e" && ev.mods === 4 && entry.options.length) { editNotes(); return true; }
              if (key === "enter" && ev.mods === 0) {
                if (entry.options.length && otherSelected && !notes && !answer.text.trim()) {
                  editing = true; notice = "Write a custom answer before submitting."; changed(); return true;
                }
                if (!editing && choices.selectedIndex() === entry.options.length && (!otherSelected || !answer.text.trim())) { otherSelected = true; notes = false; editing = true; changed(); }
                else void deliver("answered");
                return true;
              }
              if (!editing) {
                if (/^[1-9]$/u.test(key) && ev.mods === 0) {
                  const target = Number(key) - 1;
                  if (target < choices.items.length) { choices.navEdge(-1); choices.navBy(target); if (entry.multi_select) toggleChoice(); }
                  repaint(); return true;
                }
                if (key === " " && ev.mods === 0) { if (entry.multi_select) toggleChoice(); return true; }
                if ((key === "backspace" || key === "delete") && entry.multi_select) { checked.clear(); otherSelected = false; changed(); return true; }
                if (key === "down" || key === "j" || (key === "n" && ev.mods === 4)) choices.navBy(1);
                if (key === "up" || key === "k" || (key === "p" && ev.mods === 4)) choices.navBy(-1);
                if (key !== "down" && key !== "up" && key !== "j" && key !== "k" && ev.code === "char" && (ev.mods & ~1) === 0) {
                  editNotes(); answer.onKey(ev);
                }
                repaint(); return true;
              }
            }
            if (editing && entry.status === "pending") answer.onKey(ev);
            repaint();
            return true;
          },
          onMouse(ev) {
            if (heading.onMouse(ev)) { repaint(); return true; }
            if (!busy && !review && showChoices() && entry.status === "pending" && choices.onMouse(ev)) {
              if (ev.event === "press" && ev.button === "left") { editing = false; if (entry.multi_select) toggleChoice(); }
              repaint();
            }
            return true;
          },
        };
        const win = new Window({
          name: "yuke-clarify", content, outsidePress: "ignore",
          title: () => review ? "Review clarification answers" : `${entry.batch_id ? (entry.batch_index ?? 0) + 1 : index + 1}) ${entry.title} · ${entry.batch_id ? (entry.batch_index ?? 0) + 1 : index + 1}/${entry.batch_size ?? pending.length}`,
          titleGroup: "ClarifyTitle", borderGroup: "ClarifyBorder", footerGroup: "ClarifyContext",
          footer: () => {
            if (busy) return "delivering…";
            if (review) return entry.status !== "pending" ? "delivery in progress or uncertain · esc back" : confirmingUnanswered ? "enter submit with unanswered · esc back" : "enter submit all · 1–3 edit · esc back";
            if (confirmingDismiss) return "enter decline · esc keep pending";
            if (entry.status !== "pending") return "tab next · pgup/dn context · esc close";
            if (entry.batch_id) return editing ? "enter next/review · tab choices · ctrl+p/n question · esc later" : `${entry.multi_select ? "space/1–9 toggle · " : "1–9 choose · "}enter next/review · tab notes · ctrl+p/n question`;
            if (entry.multi_select) return editing ? "enter submit · ctrl+b choices · esc later" : "space/1–9 toggle · enter submit · ctrl+e notes · esc later";
            const scroll = headingRect && headingRows > headingRect.h ? "pgup/dn context · " : "";
            if (headingRect && headingRect.w < 76) return (editing ? "enter send" : "enter answer") + " · esc later · tab next" + (scroll ? " · pgup/dn context" : "");
            return scroll + (editing
              ? `enter send · ⇧enter newline · tab next · ${entry.options.length ? "ctrl+b choices" : "ctrl+d decline"} · esc later`
              : "↑↓ choose · enter answer · tab next · ctrl+d decline · esc later");
          },
          width: (max) => Math.min(100, Math.max(1, Math.floor(max * 0.85))),
          contentHeight: (max, width) => {
            const body = responsesHeight(width);
            return Math.min(max, questionRows(width).length + (body ? 1 : 0) + body);
          },
        });
        load();
        const releaseDraft = c.ctx.own(() => { clearTimeout(saveTimer); return saveDraft(); });
        close = c.tui.overlay(win, () => { opened = false; void releaseDraft(); });
      }
      c.tui.command.add("yuke-clarify:questions", {
        desc: "answer pending clarifications for this chat", slash: "questions",
        run: () => { void openInbox().catch((error) => { opened = false; if (c.ctx.alive) c.ctx.interaction.notify(String(error), "error"); }); },
      });
      c.tui.keymap.add({ "shift+left": "yuke-clarify:questions" }, "chat && !overlay");
      c.ctx.advise(c.tui.root, "onEvent", "around", (next, ev) => {
        const view = c.tui.root.active;
        if (ev.type === "key" && ev.event !== "release" && ev.code === "char" && ev.char === "h" && ev.mods === 4 &&
            view?.name === "chat" && !c.tui.root.overlays.some((layer) => layer.modal !== false)) {
          const chat = /** @type {import("yuke:chat").ChatView} */ (view);
          const sessionId = chat.session.sessionId;
          if (!initialized) {
            void initialRefresh.then(() => {
              if (!c.ctx.alive || c.tui.root.active !== view || chat.session.sessionId !== sessionId ||
                  c.tui.root.overlays.some((layer) => layer.modal !== false)) return;
              if (entries.some((item) => item.session === sessionId)) c.tui.command.perform("yuke-clarify:questions");
              else next(ev);
            });
            return;
          }
          if (entries.some((item) => item.session === sessionId)) {
            c.tui.command.perform("yuke-clarify:questions");
            return;
          }
        }
        return next(ev);
      });
}
}
  
}
