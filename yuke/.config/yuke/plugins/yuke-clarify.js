//! A quiet, persistent clarification inbox. Never borrows the chat composer.
import { client, env, exec } from "yuke";
import { currentSession } from "yuke:session";
import { Composer, List, Pager, Window } from "yuke:ui";
import { wrapRows } from "yuke:chat";
/** @import { Plugin } from "yuke" */
/** @import { Rect } from "yuke:ui" */
/** @typedef {NonNullable<NonNullable<ConstructorParameters<typeof Window>[0]>["content"]>} WindowContent */
/** @typedef {{ label: string, description: string, recommended: boolean }} Choice */
/** @typedef {{ title: string, question: string, context: string, options: Choice[] }} Question */
/** @typedef {{ text: string, selected: number, other: boolean }} Draft */
/** @typedef {Question & { id: string, session: string, status: string, draft: Draft, token?: string, answer?: string, kind?: string, error?: string }} Entry */

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
  if (Object.keys(value).some((key) => !["title", "question", "context", "options"].includes(key))) throw new Error("unknown question field");
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
  return { title, question, context, options };
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
  ].join("\n\n");
}

/** @param {string} value */
function quote(value) { return "'" + value.replaceAll("'", "'\\''") + "'"; }

/** Model tools work in every mode; keyboard and dialogs exist only in the TUI. */
export const yukeClarify = /** @type {Plugin} */ ({
  name: "yuke-clarify",
  apply(ctx) {
    const home = env.get("HOME") || ".";
    const app = env.get("YUKE_APPNAME") || "yuke";
    const config = (env.get("XDG_CONFIG_HOME") || home + "/.config") + "/" + app;
    const database = (env.get("XDG_STATE_HOME") || home + "/.local/state") + "/" + app + "/clarify/questions.sqlite3";
    /** @type {Entry[]} */
    let entries = [];
    let unavailable = false;
    let repaint = () => {};
    let tail = Promise.resolve();

    /** Serialize local operations; SQLite also arbitrates between processes. @param {string} action @param {Record<string, unknown>} [args] @returns {Promise<any>} */
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
        if (!unavailable && ctx.alive) ctx.interaction.notify("Questions unavailable: " + String(error), "error");
        unavailable = true;
      }
      if (ctx.alive) repaint();
    }
    void refresh();
    // Refresh other instances' changes, but never poll from a render callback.
    let polling = false;
    const timer = setInterval(() => {
      if (polling) return;
      polling = true;
      void refresh().finally(() => { polling = false; });
    }, 2000);
    ctx.own(() => clearInterval(timer));
    ctx.own(() => tail);

    ctx.hook("prompt.build", (payload) => ({ replace: { sections: [...payload.sections, {
      key: "yuke-clarify",
      text: "Use ask_question for decisions that require user clarification. It queues a question and returns immediately; it is not an answer or approval. Continue only independent work, never guess an answer or perform dependent actions. If blocked, explain what is waiting and end your turn. Do not repeatedly ask the same pending question. Answers arrive later as user messages marked [yuke-clarify <id>: answered] or dismissed. In the TUI the user opens questions with Shift+Left or /questions. In headless mode tell them to resume this chat in the TUI to answer.",
    }] } }));

    ctx.tools.define({
      name: "ask_question",
      description: "Queue one clarification for the user without opening a popup or waiting for an answer. Supply a short title, question, optional context, and up to 8 single-choice options (at most one recommended); omit options for free text. The user can always give a custom answer. The result is only a pending-question ID, NOT approval. Continue independent work only; stop dependent work until the user answers. Do not duplicate a pending question.",
      parameters: {
        type: "object", additionalProperties: false,
        properties: {
          title: { type: "string", maxLength: 120, description: "Short inbox title." },
          question: { type: "string", maxLength: 4000, description: "The decision the user must clarify." },
          context: { type: "string", maxLength: 4000, description: "Why the answer matters." },
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
        if (signal.aborted || !ctx.alive) throw new Error("question canceled before queueing");
        const entry = /** @type {Entry} */ (await store("add", {
          question, session: toolCtx.sessionId,
          site: `${toolCtx.sessionId}:${toolCtx.messageId}:${toolCtx.partId}`,
        }));
        await refresh();
        return JSON.stringify({ id: entry.id, status: entry.status, message: "Queued, not answered. Continue independent work only. The user can answer with Shift+Left or /questions in this chat." });
      },
    });

    ctx.inject(["chat"], (c) => {
      c.chat.render({ tools: { ask_question: (args) => ({ verb: "ask", subject: String(args.title || "clarification"), input: "" }) } });
    });

    ctx.inject(["tui"], (c) => {
      repaint = () => c.tui.root.invalidate();
      c.own(() => { repaint = () => {}; });
      c.tui.status.add({ side: "left", order: 45, render: () => {
        if (unavailable) return "questions unavailable";
        const count = entries.filter((entry) => entry.session === currentSession()?.sessionId).length;
        return count ? `${count} question${count === 1 ? "" : "s"} · ⇧←` : "";
      } });
      let opened = false;

      async function openInbox() {
        if (opened) return;
        opened = true;
        await refresh();
        const sessionId = currentSession()?.sessionId;
        const pending = entries.filter((entry) => entry.session === sessionId);
        if (!c.alive || unavailable || pending.length === 0) {
          opened = false;
          if (c.alive && !unavailable) c.interaction.notify("No pending questions in this chat.");
          return;
        }
        let index = 0;
        let entry = pending[index];
        let busy = false;
        let confirmingDismiss = false;
        let notice = "";
        let saving = false;
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
        const choices = new List({
          items: /** @type {Choice[]} */ ([]), itemHeight: 2,
          format: (choice) => ({ lines: [
            { text: choice.label + (choice.recommended ? " (recommended)" : "") },
            { text: choice.description, group: "UIDim" },
          ] }),
        });
        let editing = false;
        /** @type {Rect | null} */
        let choiceRect = null;

        function draft() {
          return { text: answer.text, selected: Math.max(0, choices.selectedIndex()), other: editing && entry.options.length > 0 };
        }
        async function saveDraft() {
          clearTimeout(saveTimer);
          if (entry.status !== "pending") return;
          const id = entry.id;
          const value = draft();
          entry.draft = value;
          try { await store("draft", { id, draft: value }); }
          catch (error) { if (c.alive) c.interaction.notify("Could not save answer draft: " + String(error), "error"); }
        }
        function changed() {
          if (saving) return;
          clearTimeout(saveTimer);
          saveTimer = setTimeout(() => { void saveDraft(); }, 250);
          repaint();
        }
        const invalidateAnswer = answer.input.onChange;
        answer.input.onChange = () => { invalidateAnswer?.(); changed(); };
        choices.onMove = changed;

        function load() {
          saving = true;
          notice = entry.error ? "Previous delivery failed; you may retry." : "";
          confirmingDismiss = false;
          heading.toTop();
          answer.text = entry.draft.text;
          editing = entry.options.length === 0 || entry.draft.other;
          choices.setItems([...entry.options, { label: "Other…", description: "Write a custom answer", recommended: false }]);
          choices.navEdge(-1);
          choices.navBy(Math.min(entry.draft.selected, entry.options.length));
          saving = false;
          repaint();
        }
        /** @param {number} direction */
        async function navigate(direction) {
          if (busy) return;
          busy = true;
          await saveDraft();
          index = (index + direction + pending.length) % pending.length;
          entry = pending[index];
          load();
          busy = false;
        }

        /** Claim before sending; no retry after an accepted input whose receipt failed to save. @param {"answered" | "dismissed"} kind */
        async function deliver(kind) {
          if (busy || entry.status !== "pending") return;
          const text = editing ? answer.text.trim() : choices.selected()?.label || "";
          if (kind === "answered" && (!text || text.length > 8000)) {
            notice = "Enter an answer (at most 8000 characters)."; repaint(); return;
          }
          busy = true;
          await saveDraft();
          if (!c.alive) { busy = false; return; }
          notice = "Sending answer…";
          repaint();
          /** @type {Entry | undefined} */
          let claim;
          let accepted = false;
          try {
            claim = /** @type {Entry} */ (await store("claim", { id: entry.id, kind, answer: kind === "dismissed" ? "" : text }));
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

        /** @type {WindowContent} */
        const content = {
          layout(rect) {
            const value = [entry.question, entry.context, notice,
              entry.status !== "pending" ? "Delivery in progress or uncertain. Automatic resend is disabled." : "",
              confirmingDismiss ? "Decline this question? Enter confirms; Esc keeps it pending." : "",
            ].filter(Boolean).join("\n\n");
            if (value !== headingText || rect.w !== headingWidth) {
              const rows = wrapRows(value, rect.w, "Normal", 0);
              headingRows = rows.length;
              heading.setRows(rows);
              if (notice || confirmingDismiss || entry.status !== "pending") heading.toBottom();
              headingText = value;
              headingWidth = rect.w;
            }
            const headerHeight = Math.min(headingRows, Math.max(1, rect.h - 6));
            headingRect = { ...rect, h: headerHeight };
            const rest = { ...rect, y: rect.y + headerHeight + 1, h: Math.max(0, rect.h - headerHeight - 1) };
            if (editing) answer.layout(rest);
            else choiceRect = rest;
          },
          draw(focused) {
            if (headingRect) heading.draw(headingRect);
            if (entry.status !== "pending" || confirmingDismiss) return;
            if (editing) answer.draw(focused);
            else if (choiceRect) choices.draw(choiceRect);
          },
          cursor: () => editing && entry.status === "pending" && !confirmingDismiss ? answer.cursor() : null,
          onKey(ev) {
            if (busy) return true;
            if (ev.type === "key" && ev.event === "release") return true;
            if (ev.type === "key") {
              const key = ev.code === "char" ? ev.char : ev.code;
              if (key === "esc" || (key === "c" && ev.mods === 4)) {
                if (confirmingDismiss) { confirmingDismiss = false; repaint(); } else close();
                return true;
              }
              if (key === "page_up" || key === "page_down") { heading.navPage(key === "page_up" ? -1 : 1); repaint(); return true; }
              if (confirmingDismiss) {
                if (key === "enter") void deliver("dismissed");
                return true;
              }
              if (key === "tab") { void navigate(ev.mods === 1 ? -1 : 1); return true; }
              if (entry.status !== "pending") return true;
              if (key === "d" && ev.mods === 4) { confirmingDismiss = true; repaint(); return true; }
              if (key === "b" && ev.mods === 4 && entry.options.length) { editing = false; changed(); return true; }
              if (key === "enter" && ev.mods === 0) {
                if (!editing && choices.selectedIndex() === entry.options.length) { editing = true; changed(); }
                else void deliver("answered");
                return true;
              }
              if (!editing) {
                if (key === "down" || key === "j" || (key === "n" && ev.mods === 4)) choices.navBy(1);
                if (key === "up" || key === "k" || (key === "p" && ev.mods === 4)) choices.navBy(-1);
                repaint(); return true;
              }
            }
            if (editing && entry.status === "pending") answer.onKey(ev);
            repaint();
            return true;
          },
          onMouse(ev) { if (heading.onMouse(ev)) { repaint(); return true; } if (!busy && !editing && entry.status === "pending") { choices.onMouse(ev); repaint(); } return true; },
        };
        const win = new Window({
          name: "yuke-clarify", content, outsidePress: "ignore",
          title: () => `${entry.title} · ${index + 1}/${pending.length}`,
          footer: () => busy ? "delivering…" : "enter answer · tab next · pgup/dn context · ctrl+b choices · ctrl+d decline · esc later",
          width: (max) => Math.min(100, Math.max(1, Math.floor(max * 0.85))),
          height: (max) => Math.max(1, Math.floor(max * 0.8)),
        });
        load();
        const releaseDraft = c.own(() => { clearTimeout(saveTimer); return saveDraft(); });
        close = c.tui.overlay(win, () => { opened = false; void releaseDraft(); });
      }
      c.tui.command.add("yuke-clarify:questions", {
        desc: "answer pending clarifications for this chat", slash: "questions",
        run: () => { void openInbox().catch((error) => { opened = false; if (c.alive) c.interaction.notify(String(error), "error"); }); },
      });
      c.tui.keymap.add({ "shift+left": "yuke-clarify:questions" }, "chat && !overlay");
    });
  },
});
