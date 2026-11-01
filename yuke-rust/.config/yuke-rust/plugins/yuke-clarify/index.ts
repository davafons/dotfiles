import type { PluginContext, SessionContext, Sessions } from "yuke:plugins";
import { Command } from "yuke:process";
import { stack, strokeOf, TextEditor, TextView, type View } from "yuke:tui";
import { command, currentSession } from "../../lib.ts";
import { markdown } from "../../views.ts";
import { answerMessage, batchAnswerMessage, validateBatch, validateQuestion } from "./questions.js";

type Question = ReturnType<typeof validateQuestion>;
type Entry = Question & {
  id: string;
  session: string;
  status: string;
  batch_id?: string;
  question_id?: string;
  batch_size?: number;
  draft: Draft;
  token?: string;
  answer?: string;
  kind?: string;
  responses?: string[];
};
interface Draft {
  text: string;
  selected: number;
  other: boolean;
  checked: number[];
  otherSelected: boolean;
  notes: boolean;
  committed: boolean;
  responses: string[];
}
interface Clarifications {
  pending: (id: string) => boolean;
  onChange: (listener: () => void) => () => void;
}
declare module "yuke:plugins" {
  interface Services {
    readonly "yuke-clarify": Clarifications;
  }
}

let database: string;
let sessions: Sessions;
let entries: Entry[] = [];
let pending = new Set<string>();
const listeners = new Set<() => void>();
let refresh: () => Promise<void> = async () => {};

async function store<T>(action: string, value: unknown, signal: AbortSignal): Promise<T> {
  const output = await new Command("python3", {
    args: [`${import.meta.dirname}/../../helpers/yuke-clarify-store.py`, database, action, JSON.stringify(value)],
    cwd: database.slice(0, database.lastIndexOf("/")),
    signal,
  }).output();
  signal.throwIfAborted();
  const decoder = new TextDecoder();
  if (!output.success) throw new Error(decoder.decode(output.stderr));
  return JSON.parse(decoder.decode(output.stdout)) as T;
}

/** Provide a persistent clarification inbox. Question tools return before an answer and never open a modal themselves. */
export async function apply(ctx: PluginContext): Promise<(() => Promise<void>) | undefined> {
  database = `${ctx.dataDir}/questions.sqlite3`;
  sessions = ctx.get("sessions");
  const tui = ctx.get("tui");
  let pendingWrites: Promise<void> = Promise.resolve();
  const rows = new Map<string, readonly { readonly text: string }[]>();
  const noRows: never[] = [];
  refresh = async () => {
    const next = await store<Entry[]>("list", {}, ctx.signal);
    if (ctx.signal.aborted) return;
    entries = next;
    const changed = new Set(entries.map((entry) => entry.session));
    const different = changed.size !== pending.size || [...changed].some((id) => !pending.has(id));
    pending = changed;
    rows.clear();
    for (const id of pending)
      rows.set(id, [
        { text: `${entries.filter((entry) => entry.session === id).length} questions waiting · /questions` },
      ]);
    if (different)
      listeners.forEach((listener) => {
        listener();
      });
    tui?.requestFrame();
  };
  ctx.provide("yuke-clarify", {
    pending: (id) => pending.has(id),
    onChange: (listener) => {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
  });
  await refresh();
  if (tui === undefined) return;
  const stopRows = ctx
    .get("chat")
    .addComposerRows("below", (pane) => (pane.session === undefined ? noRows : (rows.get(pane.session) ?? noRows)));
  ctx.signal.addEventListener("abort", stopRows, { once: true });
  const deliver = async (entry: Entry, batch: boolean, allowUnanswered: boolean, dismiss = false): Promise<void> => {
    await pendingWrites;
    let attempted = false;
    const controller = new AbortController();
    try {
      const handle = await sessions.open(entry.session, {
        tail: 0,
        signal: AbortSignal.any([ctx.signal, controller.signal]),
        event: () => {},
      });
      if (batch) {
        const value = await store<Parameters<typeof batchAnswerMessage>[0]>(
          "claim_batch",
          { id: entry.batch_id, allow_unanswered: allowUnanswered, dismiss },
          ctx.signal,
        );
        attempted = true;
        const input = await handle.input([{ user_text: batchAnswerMessage(value) }]);
        await store("finish_batch", { id: value.id, token: value.token, input_id: input }, ctx.signal);
      } else {
        const responses = dismiss ? [] : entry.draft.responses;
        const value = await store<Entry>(
          "claim",
          { id: entry.id, kind: dismiss ? "dismissed" : "answered", answer: responses.join("\n"), responses },
          ctx.signal,
        );
        attempted = true;
        const input = await handle.input([{ user_text: answerMessage(value) }]);
        await store("finish", { id: value.id, token: value.token, input_id: input }, ctx.signal);
      }
    } catch (error) {
      if (attempted) throw new Error(`Answer delivery is uncertain. Automatic resend is disabled. ${String(error)}`);
      throw error;
    } finally {
      controller.abort();
      await refresh();
    }
  };
  const open = async (): Promise<void> => {
    await refresh();
    const id = currentSession(ctx, tui);
    const candidates = entries.filter((entry) => entry.session === id);
    const first =
      candidates[0] ??
      (await tui.select({
        title: "Question inbox",
        items: entries,
        label: (entry) => `${entry.title} · ${entry.session}`,
        signal: ctx.signal,
      }));
    if (first === undefined) {
      ctx.notify("info", "No pending questions.");
      return;
    }
    const questions =
      first.batch_id === undefined ? [first] : entries.filter((entry) => entry.batch_id === first.batch_id);
    let index = 0;
    let selected = 0;
    let checked = new Set<number>();
    let notice = "";
    let busy = false;
    let review = false;
    let loading = false;
    let draftTimer: ReturnType<typeof setTimeout> | undefined;
    const heading = new TextView({ document: markdown("question", "") });
    const editor = new TextEditor({ placeholder: "Type notes or a custom answer…" });
    const choices: View = {
      draw: (canvas) => {
        const entry = questions[index];
        if (entry === undefined || review) return;
        const first = Math.max(0, selected - Math.floor(canvas.height / 2) + 1);
        for (let row = 0; row < Math.ceil(canvas.height / 2) && row + first <= entry.options.length; row += 1) {
          const number = row + first;
          const option = entry.options[number];
          const label =
            option === undefined ? "Other…" : `${option.label}${option.recommended ? " (Recommended)" : ""}`;
          const mark = entry.multi_select ? (checked.has(number) ? "[x]" : "[ ]") : selected === number ? "›" : " ";
          const style = selected === number ? "picker.selected" : undefined;
          if (selected === number) canvas.fill(0, row * 2, canvas.width, 2, style);
          canvas.text(1, row * 2, `${mark} ${number + 1}. ${label}`, style);
          canvas.text(5, row * 2 + 1, option?.description ?? "Type a custom answer below.", style ?? "chat.meta");
        }
      },
      mouse: (event) => {
        const entry = questions[index];
        if (entry === undefined || event.action !== "press" || event.button !== "left" || busy || review) return false;
        const first = Math.max(0, selected - Math.floor(Math.min(18, 2 * (entry.options.length + 1)) / 2) + 1);
        selected = Math.min(entry.options.length, first + Math.floor(event.row / 2));
        if (entry.multi_select && !checked.delete(selected)) checked.add(selected);
        changed();
        redraw();
        return true;
      },
    };
    const redraw = (): void => {
      const entry = questions[index];
      if (entry === undefined) return;
      const text = review
        ? questions
            .map(
              (entry) =>
                `### ${entry.title}\n${entry.draft.responses.join("\n") || "Unanswered. This is not approval."}`,
            )
            .join("\n\n")
        : `### ${entry.question}\n\n${entry.context}\n\n${notice}${entry.status === "pending" ? "" : "\nDelivery is in progress or uncertain. Automatic resend is disabled."}`;
      heading.setDocument(markdown("question", text));
      tui.requestFrame();
    };
    const load = (): void => {
      const entry = questions[index];
      if (entry === undefined) return;
      selected = entry.draft.selected;
      checked = new Set(entry.draft.checked);
      loading = true;
      editor.reset({
        text: entry.draft.text,
        selection: { anchor: entry.draft.text.length, head: entry.draft.text.length },
        spans: [],
      });
      loading = false;
      redraw();
    };
    const save = async (): Promise<void> => {
      const entry = questions[index];
      if (busy || entry === undefined || entry.status !== "pending" || review) return;
      const custom = selected === entry.options.length || entry.options.length === 0;
      const labels = entry.multi_select
        ? [...checked]
            .filter((number) => number < entry.options.length)
            .map((number) => entry.options[number]?.label ?? "")
        : custom
          ? []
          : [entry.options[selected]?.label ?? ""];
      const text = editor.state.text.trim();
      if (labels.length === 0 && text === "") {
        notice = "Choose an option or type an answer.";
        redraw();
        return;
      }
      busy = true;
      if (draftTimer !== undefined) clearTimeout(draftTimer);
      try {
        await pendingWrites;
        entry.draft = {
          text,
          selected,
          checked: [...checked],
          other: custom,
          otherSelected: custom,
          notes: !custom && text !== "",
          committed: true,
          responses: [...labels, ...(text === "" ? [] : [labels.length === 0 ? text : `user_note: ${text}`])],
        };
        await store("draft", { id: entry.id, draft: entry.draft }, ctx.signal);
        if (index < questions.length - 1) {
          index += 1;
          load();
        } else {
          review = true;
          redraw();
        }
      } finally {
        busy = false;
      }
    };
    const persist = (): void => {
      if (draftTimer !== undefined) clearTimeout(draftTimer);
      draftTimer = undefined;
      const entry = questions[index];
      if (entry === undefined || entry.status !== "pending" || review) return;
      const draft = entry.draft;
      pendingWrites = pendingWrites
        .catch((error: unknown) => {
          if (!ctx.signal.aborted) ctx.notify("error", String(error));
        })
        .then(async () => {
          await store("draft", { id: entry.id, draft }, AbortSignal.timeout(5000));
        });
      void pendingWrites.catch((error: unknown) => {
        if (!ctx.signal.aborted) ctx.notify("error", String(error));
      });
    };
    const changed = (): void => {
      const entry = questions[index];
      if (loading || busy || review || entry === undefined || entry.status !== "pending") return;
      entry.draft = {
        ...entry.draft,
        text: editor.state.text,
        selected,
        checked: [...checked],
        committed: false,
        responses: [],
      };
      if (draftTimer !== undefined) clearTimeout(draftTimer);
      draftTimer = setTimeout(persist, 250);
    };
    const submit = async (allowUnanswered = false): Promise<void> => {
      if (busy) return;
      if (questions.some((entry) => !entry.draft.committed) && !allowUnanswered) {
        const confirm = tui.dialog({
          title: () => "Submit with unanswered questions? Unanswered means no approval.",
          body: new TextView({
            document: markdown("unanswered", "Dependent work must stay blocked for every unanswered question."),
          }),
          rows: 5,
          signal: dialog.signal,
          keys: [
            {
              key: "enter",
              label: "submit partial answers",
              run: () => {
                confirm.close();
                void submit(true).catch(failed);
              },
            },
          ],
        });
        return;
      }
      busy = true;
      try {
        await deliver(
          first,
          first.batch_id !== undefined,
          allowUnanswered,
          first.batch_id === undefined && allowUnanswered && !first.draft.committed,
        );
        dialog.close();
      } finally {
        busy = false;
      }
    };
    const failed = (error: unknown): void => {
      notice = String(error);
      redraw();
    };
    const body = {
      ...stack("column", [
        { view: heading, size: "fill" },
        { view: choices, size: () => (review ? 0 : Math.min(18, 2 * ((questions[index]?.options.length ?? 0) + 1))) },
        { view: editor, size: () => (review ? 0 : 3) },
      ]),
      initialFocus: editor,
    };
    const dialog = tui.dialog({
      title: () => `Questions · ${review ? "Review" : `${index + 1}/${questions.length}`} · ${first.title}`,
      body,
      rows: Math.max(12, tui.height - 2),
      keys: [
        {
          key: "ctrl+o",
          label: "move to this chat",
          when: () => !busy && first.status === "pending",
          run: () => {
            const move = async (): Promise<void> => {
              const target = await ctx.get("chat").start();
              if (target === undefined || target === first.session) return;
              const confirm = tui.dialog({
                title: () => "Move these pending questions to this chat?",
                body: new TextView({
                  document: markdown(
                    "move-question",
                    `Original session: ${first.session}\n\nTarget session: ${target}\n\nFuture answers go only to the target. The old chat history is not imported. Original question IDs and drafts stay the same.`,
                  ),
                }),
                rows: 10,
                signal: dialog.signal,
                keys: [
                  {
                    key: "enter",
                    label: "move questions",
                    run: () => {
                      confirm.close();
                      persist();
                      void pendingWrites
                        .then(() =>
                          store(
                            first.batch_id === undefined ? "adopt" : "adopt_batch",
                            { id: first.batch_id ?? first.id, session: target },
                            ctx.signal,
                          ),
                        )
                        .then(() => {
                          dialog.close();
                          return open();
                        })
                        .catch(failed);
                    },
                  },
                ],
              });
            };
            void move().catch(failed);
          },
        },
        {
          key: "ctrl+d",
          label: "dismiss",
          when: () => !busy && first.status === "pending",
          run: () => {
            const confirm = tui.dialog({
              title: () => "Dismiss without answers? This gives no approval.",
              body: new TextView({
                document: markdown(
                  "dismiss",
                  "The originating session receives an explicit dismissed or unanswered receipt. Dependent work must stay blocked.",
                ),
              }),
              rows: 6,
              signal: dialog.signal,
              keys: [
                {
                  key: "enter",
                  label: "dismiss",
                  run: () => {
                    confirm.close();
                    busy = true;
                    persist();
                    void deliver(first, first.batch_id !== undefined, true, true)
                      .then(() => dialog.close())
                      .catch(failed)
                      .finally(() => {
                        busy = false;
                      });
                  },
                },
              ],
            });
          },
        },
        {
          key: "ctrl+s",
          label: "submit",
          when: () => !busy && first.status === "pending",
          run: () => {
            void submit().catch(failed);
          },
        },
        {
          key: "enter",
          label: "submit reviewed answers",
          when: () => review && !busy,
          run: () => {
            void submit().catch(failed);
          },
        },
        {
          key: "alt+left",
          label: "previous",
          when: () => !busy && (index > 0 || review),
          run: () => {
            if (!review) {
              persist();
              index -= 1;
            }
            review = false;
            load();
          },
        },
      ],
    });
    const extension = editor.extend(dialog.signal);
    extension.onChange(changed);
    dialog.signal.addEventListener("abort", persist, { once: true });
    extension.onKey((event) => {
      const stroke = strokeOf(event);
      const entry = questions[index];
      if (entry === undefined) return false;
      if (stroke === "enter") {
        if (review) {
          void submit().catch(failed);
        } else {
          void save().catch(failed);
        }
        return true;
      }
      if (review || entry.options.length === 0) return false;
      if (stroke === "up") selected = Math.max(0, selected - 1);
      else if (stroke === "down" || stroke === "tab") selected = Math.min(entry.options.length, selected + 1);
      else if (stroke === "space" && entry.multi_select && editor.state.text === "") {
        if (!checked.delete(selected)) checked.add(selected);
      } else if (
        /^[1-9]$/.test(stroke) &&
        editor.state.text === "" &&
        selected !== entry.options.length &&
        Number(stroke) <= entry.options.length + 1
      ) {
        selected = Number(stroke) - 1;
        if (entry.multi_select) {
          if (!checked.delete(selected)) checked.add(selected);
        } else {
          void save().catch(failed);
        }
      } else return false;
      changed();
      redraw();
      return true;
    }, "beforeKeymap");
    load();
    tui.focus(editor);
  };
  command(ctx, tui, "questions", "Open the clarification inbox", open);
  tui.keys.bind("shift+left", "questions", { in: "chat" });
  return async () => {
    await pendingWrites;
  };
}

/** Register nonblocking question tools. A pending receipt never supplies an answer or approval. */
export function session(s: SessionContext): undefined {
  s.hook("prompt.build", (event) => ({
    sections: {
      ...event.sections,
      clarification:
        "Use ask_question or request_user_input for decisions that need the user. They queue immediately and return a pending ID. A queued question is not an answer or approval. Continue independent work only. Keep dependent work blocked until the answer arrives. Do not repeat a pending question. The user opens /questions. Answers arrive as user messages with a yuke-clarify correlation ID.",
    },
  }));
  const option = {
    type: "object",
    properties: { label: { type: "string" }, description: { type: "string" }, recommended: { type: "boolean" } },
    required: ["label"],
  } as const;
  const fields = {
    question: { type: "string" },
    context: { type: "string" },
    multi_select: { type: "boolean" },
    options: { type: "array", items: option },
  } as const;
  s.tools.define({
    name: "ask_question",
    description:
      "Queue one clarification without opening a popup or waiting. Supply title, question, optional context, and up to eight options. The user can enter a custom answer. A pending receipt is not approval. Continue independent work only.",
    concurrency: "serial",
    parameters: {
      type: "object",
      properties: { ...fields, title: { type: "string" } },
      required: ["title", "question"],
    },
    execute: async (args, context) => {
      const question = validateQuestion(args);
      const entry = await store<Entry>(
        "add",
        { question, session: s.sessionId, site: `${s.sessionId}:${context.callId}` },
        context.signal,
      );
      await refresh();
      return JSON.stringify({
        id: entry.id,
        status: entry.status,
        message: "Queued, not answered. Continue independent work only. The user opens /questions.",
      });
    },
  });
  s.tools.define({
    name: "request_user_input",
    description:
      "Queue one to three related questions with short headers and stable snake_case IDs. The user can choose options, add notes or a custom answer, review, and submit the batch together. This returns a pending ID, not answers or approval. Do not include an Other option; the UI supplies it.",
    concurrency: "serial",
    parameters: {
      type: "object",
      properties: {
        questions: {
          type: "array",
          items: {
            type: "object",
            properties: { ...fields, id: { type: "string" }, header: { type: "string" } },
            required: ["id", "header", "question"],
          },
        },
      },
      required: ["questions"],
    },
    execute: async (args, context) => {
      const questions = validateBatch(args);
      const batch = await store<{ id: string; status: string }>(
        "add_batch",
        { questions, session: s.sessionId, site: `${s.sessionId}:${context.callId}` },
        context.signal,
      );
      await refresh();
      return JSON.stringify({
        id: batch.id,
        status: batch.status,
        message:
          "Queued, not answered. Continue independent work only. The user opens /questions and submits the batch together.",
      });
    },
  });
}
