//! WORD navigation through bundled transcript motions. The bundled layer keeps its cursor and selection.
import { ChatView } from "yuke:chat";
import { keys } from "yuke:ui";
const DIGIT = /^[1-9]$/u;
const COUNTED_MOTIONS = new Set(["h", "l", "j", "k", "w", "b", "e", "{", "}", "J", "K"]);
/** @import { InjectContext } from "yuke" */
/** @import { createVimText } from "./vim-text.js" */

/** Add transcript W/B. Native motions keep visual selection, source anchors, and scrolling in sync. */
export function installTranscriptWords(
  /** @type {InjectContext} */ c,
  /** @type {ReturnType<typeof createVimText>} */ nav,
  /** @type {typeof c.tui.keymap} */ shared,
) {
  let digits = "";
  /** @param {ChatView} view @param {string} stroke @param {Parameters<typeof shared.onKey>[0]} ev */
  function native(view, stroke, ev) {
    const before = view.transcript.caret;
    shared._perform(stroke, ev);
    const after = view.transcript.caret;
    return !!after && (!before || before.id !== after.id || before.row !== after.row || before.col !== after.col);
  }
  /** @param {ChatView} view @param {boolean} forward @param {Parameters<typeof shared.onKey>[0]} ev */
  function word(view, forward, ev) {
    const transcript = view.transcript;
    if (!transcript.caret) shared._perform("0", ev);
    const initial = transcript.caret;
    if (!initial) return;
    let body = transcript.rowTextAt(initial.id, initial.row);
    let target = forward ? nav.wordStart(body, initial.col, true) : nav.wordBack(body, initial.col, true);
    if (forward ? target >= body.length : initial.col === 0 || (target === 0 && nav.cls(body, 0, true) === 0)) {
      // Move across rows with native motions, not direct writes to the bundled cursor.
      for (;;) {
        const previous = transcript.caret;
        shared._perform(forward ? "j" : "k", ev);
        const at = transcript.caret;
        if (!at || !previous || (at.id === previous.id && at.row === previous.row)) return;
        shared._perform(forward ? "0" : "$", ev);
        body = transcript.rowTextAt(at.id, at.row);
        if (!body.length) return;
        if (!body.trim()) continue;
        target = forward ? (nav.cls(body, 0, true) === 0 ? nav.wordStart(body, 0, true) : 0) : nav.wordBack(body, body.length, true);
        break;
      }
    }
    for (;;) {
      const at = transcript.caret;
      if (!at || (forward ? at.col >= target : at.col <= target)) return;
      // Each WORD boundary is also a word boundary. Skip punctuation boundaries with native w/b.
      if (!native(view, forward ? "w" : "b", ev)) return;
    }
  }
  c.advise(shared, "onKey", "around", (next, ev) => {
    const view = c.tui.root.active;
    if (!(view instanceof ChatView) || view.focus !== "transcript" || c.tui.root.focused !== c.tui.root.active || ev.event === "release") return next(ev);
    const stroke = keys.strokeOf(ev);
    if (!shared.pending && (DIGIT.test(stroke) || (stroke === "0" && digits))) {
      digits += stroke;
      if (Number(digits) > 10000) { digits = ""; c.interaction.notify("Vim count exceeds 10000", "warn"); }
      return true;
    }
    const count = Number(digits) || 1;
    digits = "";
    if (!shared.pending && (stroke === "W" || stroke === "B")) {
      for (let n = 0; n < count; n++) word(view, stroke === "W", ev);
      return true;
    }
    if (!shared.pending && COUNTED_MOTIONS.has(stroke)) {
      for (let n = 0; n < count; n++) next(ev);
      return true;
    }
    return next(ev);
  });
  c.on("region.focused", () => { digits = ""; });
  c.on("pane.focused", () => { digits = ""; });
}
