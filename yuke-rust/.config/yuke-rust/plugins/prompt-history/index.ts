import type { Frozen, PluginContext } from "yuke:plugins";
import type { Block } from "yuke:protocol";
import { Transcript } from "yuke:transcript";
import { type EditorSpan, type EditorState, strokeOf, TextEditor } from "yuke:tui";
import { command, currentSession, focusedEditor } from "../../lib.ts";
import type {} from "../vim/src/service.ts";

/** Reconstruct an editable user input with its image references. The caller owns the draft. */
export function draftOf(content: readonly Frozen<Block>[]): EditorState {
  let text = "";
  const spans: EditorSpan[] = [];
  for (const block of content) {
    if ("user_text" in block) text += block.user_text;
    else if ("media" in block) {
      spans.push({
        from: text.length,
        to: text.length + 1,
        kind: "image",
        label: `[image ${spans.length + 1}]`,
        media: block.media,
      });
      text += "\uFFFC";
    }
  }
  return { text, spans, selection: { anchor: text.length, head: text.length } };
}

/** Preserve the unsent draft while browsing user prompts. History reads happen only on request. */
export function apply(ctx: PluginContext): undefined {
  const tui = ctx.get("tui");
  const vim = ctx.get("composer-vim");
  if (tui === undefined || vim === undefined) return;
  const sessions = ctx.get("sessions");
  const read = async (id: string): Promise<EditorState[]> => {
    const transcript = new Transcript();
    let before: number | undefined;
    for (;;) {
      const page = await sessions.events(id, { limit: 200, ...(before === undefined ? {} : { before }) });
      transcript.insert(page);
      if (page.length < 200) break;
      before = page[0]?.seq;
    }
    return transcript.entries.flatMap((entry) =>
      entry.kind === "input" && entry.source.kind === "user" && entry.inputKind === "message"
        ? [draftOf(entry.content)]
        : [],
    );
  };
  command(ctx, tui, "history", "Browse sent prompts", async () => {
    const editor = focusedEditor(tui);
    const id = currentSession(ctx, tui);
    if (editor === undefined || id === undefined) return;
    const items = (await read(id)).map((draft) => ({ draft }));
    const selected = await tui.select({
      title: "Prompt history",
      items: items.toReversed(),
      label: (item) => item.draft.text.replace(/\s+/g, " "),
      signal: ctx.signal,
    });
    if (selected !== undefined) editor.reset(selected.draft);
  });
  tui.keys.bind("ctrl+x p", "history", { in: "chat" });
  tui.widgets.watch((mount) => {
    const editor = mount.widget;
    if (!(editor instanceof TextEditor) || editor.role !== "composer") return;
    const extension = editor.extend(mount.signal);
    let history:
      | { readonly id: string; readonly prompts: readonly EditorState[]; readonly draft: EditorState; index: number }
      | undefined;
    let loading = false;
    let changing = false;
    const navigate = async (direction: -1 | 1): Promise<void> => {
      const pane = mount.pane;
      const id = pane === undefined ? undefined : ctx.get("chat").session(pane.view);
      if (id === undefined || loading) return;
      if (history === undefined || history.id !== id) {
        if (direction > 0) return;
        const draft = editor.state;
        loading = true;
        let prompts: EditorState[];
        try {
          prompts = await read(id);
        } finally {
          loading = false;
        }
        if (mount.signal.aborted || ctx.signal.aborted || editor.state !== draft || tui.focused !== editor) return;
        history = { id, prompts, draft, index: prompts.length };
      }
      history.index = Math.max(0, Math.min(history.prompts.length, history.index + direction));
      const draft = history.prompts[history.index] ?? history.draft;
      changing = true;
      try {
        editor.reset(draft);
      } finally {
        changing = false;
      }
    };
    extension.onChange(() => {
      if (!changing) history = undefined;
    });
    extension.onKey((event) => {
      const stroke = strokeOf(event);
      let direction: -1 | 1;
      if (stroke === "ctrl+k") direction = -1;
      else if (stroke === "ctrl+j" && vim.mode(editor) !== "insert") direction = 1;
      else if (stroke === "up" && editor.rows.point(editor.caret)?.row === 0) direction = -1;
      else if (stroke === "down" && editor.rows.point(editor.caret)?.row === editor.rows.count - 1) direction = 1;
      else return false;
      void navigate(direction).catch((error: unknown) => ctx.notify("error", String(error)));
      return true;
    }, "beforeKeymap");
    return () => extension.dispose();
  });
  const working = new Map<string, readonly { text: string; style: string }[]>();
  const noRows: never[] = [];
  ctx.on("session.update", (event) => {
    const update = event.update;
    if (
      update.sessionUpdate === "input_accepted" &&
      update.input.source.kind === "user" &&
      update.input.kind === "message"
    ) {
      working.set(event.sessionId, [
        { text: `working  ${draftOf(update.input.content).text.replace(/\s+/g, " ")}`, style: "chat.meta" },
      ]);
    } else if (update.sessionUpdate === "state" && update.state === "idle") working.delete(event.sessionId);
    else return;
    tui.requestFrame();
  });
  const stopRows = ctx.get("chat").addComposerRows("above", (pane) => {
    const prompt = pane.session === undefined ? undefined : working.get(pane.session);
    return prompt ?? noRows;
  });
  ctx.signal.addEventListener("abort", stopRows, { once: true });
}
