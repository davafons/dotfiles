//! Navigate sent prompts from the composer and show the active prompt above it.
import { events } from "yuke";
import { ChatView } from "yuke:chat";
import { Session, sessions } from "yuke:session";
import { Composer, clip, ui } from "yuke:ui";
/** @typedef {ReturnType<Composer["snapshot"]>} ComposerSnapshot */

/** @typedef {{ snapshot: ComposerSnapshot, summary: string }} PromptEntry */

/** Rebuild editable text and image spans from one user input. @param {readonly Wire.ContentPart[]} parts @returns {PromptEntry} */
function promptEntry(parts) {
  let text = "";
  /** @type {ComposerSnapshot["spans"]} */
  const spans = [];
  /** @type {string[]} */
  const summary = [];
  for (const part of parts) {
    if (part.type === "text") {
      text += part.text;
      summary.push(part.text);
    } else if (part.type === "image") {
      const start = text.length;
      text += "[attached image]";
      spans.push({ start, end: text.length, blob: part.source });
      summary.push("[image]");
    } else if (part.type === "audio") summary.push("[audio]");
    else if (part.type === "file") summary.push(part.filename ? "[file: " + part.filename + "]" : "[file]");
  }
  return { snapshot: { text, spans }, summary: summary.join("").replace(/\s+/gu, " ").trim() };
}

/** Make a prompt fit one display row. @param {string} prompt @param {number} width */
function promptSummary(prompt, width) {
  const oneLine = prompt.replace(/\s+/gu, " ").trim();
  return clip("working  " + oneLine, Math.max(0, width), true);
}

/** Read user-authored prompts from a pane, oldest first. Engine-generated inputs have a source and are omitted. @param {ChatView} view */
function sentPrompts(view) {
  /** @type {PromptEntry[]} */
  const prompts = [];
  for (const message of view.transcript.messages()) {
    if (message.type !== "user" || message.source) continue;
    const parts = /** @type {readonly Wire.ContentPart[]} */ (view.transcript.partsOf(message.id));
    const prompt = promptEntry(parts);
    if (prompt.snapshot.text !== "") prompts.push(prompt);
  }
  return prompts;
}

/** @typedef {{ prompts: PromptEntry[], index: number, draft: ComposerSnapshot, caret: number }} HistoryState */

/** Sent-prompt history for the composer, with the current unsent draft as the newest entry. */
/** Preserve the personal prompt-history workflow with the one Vim service. No TUI or editor skips it; host failures throw. @param {import("yuke").Context} ctx */
export default function (ctx) {
  const tuiBorrow = ctx.get("tui"), vimBorrow = ctx.get("composer-vim");
  if (!tuiBorrow || !vimBorrow) return;
  const tui = tuiBorrow, vim = vimBorrow;
  /** @type {WeakMap<Composer, HistoryState>} */
  const states = new WeakMap();
  const changing = new WeakSet();
  /** The prompt that started a run, before its transcript refresh arrives. @type {WeakMap<Session, { prompt: string, previous: string | undefined }>} */
  const activePrompts = new WeakMap();

  /** Replace composer text without treating the replacement as a user edit. @param {Composer} composer @param {() => void} replace */
  function replaceComposer(composer, replace) {
    changing.add(composer);
    try { replace(); } finally { changing.delete(composer); }
  }

  /** The active chat pane, including a fresh draft that currentPane() does not report. @returns {ChatView | null} */
  function activePane() {
    const pane = tui.root.active;
    return pane instanceof ChatView ? pane : null;
  }

  /** @param {-1 | 1} direction */
  function navigate(direction) {
    const pane = activePane();
    const composer = pane?.composer;
    if (!pane || !composer || pane.focus !== "composer") return false;

    let state = states.get(composer);
    if (!state) {
      const prompts = sentPrompts(pane);
      if (direction > 0 || prompts.length === 0) return true;
      state = { prompts, index: prompts.length, draft: composer.snapshot(), caret: composer.input.caret };
      states.set(composer, state);
    }

    if (direction < 0) {
      if (state.index > 0) state.index--;
      const prompt = state.prompts[state.index];
      replaceComposer(composer, () => {
        composer.replaceSnapshot(prompt.snapshot);
      });
      return true;
    }

    if (state.index < state.prompts.length - 1) {
      state.index++;
      const prompt = state.prompts[state.index];
      replaceComposer(composer, () => {
        composer.replaceSnapshot(prompt.snapshot);
      });
      return true;
    }

    replaceComposer(composer, () => {
      composer.replaceSnapshot(state.draft, state.caret);
    });
    states.delete(composer);
    return true;
  }

  ctx.on("composer.changed", (composer) => {
    if (!changing.has(composer)) states.delete(composer);
  });
  ctx.on("composer.attached", (composer) => states.delete(composer));

  tui.keymap.add({
    up: () => navigate(-1),
    down: () => navigate(1),
    "ctrl+k": () => navigate(-1),
    "ctrl+j": () => navigate(1),
  }, "composer && vim_mode == normal && !overlay");

  // Insert-mode composers consume arrows even when the caret is already at an edge.
  // Try their multiline movement first, then fall back to prompt history if it did not move.
  ctx.advise(Composer.prototype, "onKey", "around", function (next, ev) {
    if (vim.mode(this) !== "insert") return next(ev);
    const control = ev.type === "key" && ev.event !== "release" && ev.code === "char" && ev.mods === 4
      ? ev.char
      : "";
    if (control === "k") return navigate(-1) || next(ev);
    const direction = ev.type === "key" && ev.event !== "release" && ev.mods === 0
      ? ev.code === "up" ? -1 : ev.code === "down" ? 1 : 0
      : 0;
    if (!direction) return next(ev);
    const before = this.input.caret;
    const handled = next(ev);
    if (this.input.caret !== before) return handled;
    return navigate(/** @type {-1 | 1} */ (direction)) || handled;
  });

  ctx.on("prompt-history:control-key", ev => {
    const pane = activePane();
    if (!pane || pane.focus !== "composer" || tui.root.overlays.some(layer => layer.modal !== false) || ev.char !== "j" && ev.char !== "k") return false;
    if (vim.mode(pane.composer) !== "normal" && ev.char === "j") return false;
    return navigate(ev.char === "k" ? -1 : 1);
  });
  const sharedKeymap = /** @type {typeof tui.keymap} */ (Object.getPrototypeOf(tui.keymap));
  ctx.advise(sharedKeymap, "onKey", "around", (next, ev) => {
    const pane = activePane();
    if (!pane || tui.root.focused !== pane || pane.focus !== "composer" || ev.event === "release" || tui.root.overlays.some(layer => layer.modal !== false)) return next(ev);
    const mode = vim.mode(pane.composer);
    if (ev.code === "char" && ev.mods === 4 && (ev.char === "k" || ev.char === "j" && mode === "normal")) {
      vim.cancel(pane.composer); sharedKeymap.pending = null;
      return navigate(ev.char === "k" ? -1 : 1) || next(ev);
    }
    if (mode === "normal" && ev.mods === 0 && (ev.code === "up" || ev.code === "down") && !vim.pending(pane.composer)) {
      const before = pane.composer.input.caret, direction = ev.code === "up" ? -1 : 1;
      pane.composer.moveRow(direction);
      if (pane.composer.input.caret !== before) return true;
      return navigate(direction) || next(ev);
    }
    return next(ev);
  }, { order: -200 });

  tui.command.add("prompt-history:show", {
    desc: "browse sent prompts",
    slash: "history",
    run: () => {
      const pane = activePane();
      if (!pane) return;
      const prompts = sentPrompts(pane);
      if (prompts.length === 0) {
        ctx.interaction.notify("No sent prompts in this chat.");
        return;
      }
      const items = prompts.map((prompt, index) => ({ prompt, number: index + 1 })).reverse();
      const { win } = ui.pick({
        title: "Prompt history",
        footer: "ctrl+j/k move · type to filter · enter restore · esc close",
        width: (max) => Math.max(1, Math.floor(max * 0.85)),
        height: (max) => Math.max(1, Math.floor(max * 0.7)),
        items,
        keymap: { "ctrl+j": "next", "ctrl+k": "prev" },
        filterText: (item) => item.prompt.summary,
        format: (item) => ({
          text: item.prompt.summary,
          right: "#" + item.number,
          group: "UIItem",
        }),
        onAccept: (item) => {
          const target = activePane();
          if (!target) return;
          states.delete(target.composer);
          replaceComposer(target.composer, () => {
            target.composer.replaceSnapshot(item.prompt.snapshot);
          });
          target.focusRegion("composer");
          vim.setMode(target.composer, "normal");
        },
      });
      tui.overlay(win);
    },
  });

  // Remember an accepted input immediately. Queued inputs do not replace the prompt
  // currently being worked because their session was already active before send().
  ctx.advise(Session.prototype, "send", "around", function (next, content, composer) {
    const startsRun = !this.activity || this.activity.state.type === "idle";
    const accepted = next(content, composer);
    if (accepted && startsRun) {
      const prompt = promptEntry(content).summary;
      const view = this.views.find((candidate) => candidate.composer === composer);
      const previous = view ? sentPrompts(/** @type {ChatView} */ (view)).at(-1)?.summary : undefined;
      if (prompt) activePrompts.set(this, { prompt, previous });
    }
    return accepted;
  });
  ctx.on("activity.changed", (sessionId, activity) => {
    if (activity?.state.type !== "idle") return;
    const session = sessions.find((candidate) => candidate.sessionId === sessionId);
    if (session) activePrompts.delete(session);
  });

  // Preserve the built-in queued-input rows and append the active prompt beneath them.
  ctx.advise(events, "bail", "around", (next, name, ...args) => {
    const answer = next(name, ...args);
    if (name !== "chat.strip") return answer;
    const view = /** @type {ChatView} */ (args[0]);
    const activity = view.session.activity;
    if (!activity || activity.state.type === "idle") return answer;
    const prompts = sentPrompts(view);
    const latest = prompts[prompts.length - 1]?.summary;
    const pending = activePrompts.get(view.session);
    const prompt = pending && latest === pending.previous ? pending.prompt : latest || pending?.prompt;
    if (pending && latest !== pending.previous) activePrompts.delete(view.session);
    if (!prompt) return answer;
    const row = { text: promptSummary(prompt, view.rect.w), group: "UIDim" };
    return [...(Array.isArray(answer) ? answer : []), row];
  });
}
