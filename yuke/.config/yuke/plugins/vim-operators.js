//! Composer Vim grammar, history, visual selection, and repeat-change support.
import { ChatView } from "yuke:chat";
import { Composer, keys, text as paintText, measure } from "yuke:ui";
import { createVimText } from "./vim-text.js";
import { createVimEdits } from "./vim-edits.js";
import { installTranscriptWords } from "./vim-transcript.js";
/** @import { InjectContext } from "yuke" */
/** @typedef {{ text: string, spans: Readonly<ReturnType<Composer["snapshot"]>["spans"]>, caret: number }} Snapshot */
/** @typedef {{ offset: number, remove: number, text: string }} Patch */
/** @typedef {{ command: string, operator: string, motion: string, count: number, char: string, patch: Patch | null, size: number, lines: boolean, counted: boolean, edits: (number | string)[] | null }} Recipe */
/** @typedef {{ range: { from: number, to: number, target: number, lines: boolean }, marks: Map<string, number> | null, search: { value: string, forward: boolean, whole: boolean } | null, register: string, replace: { to: number, off: (() => void) | null, edits: (number | string)[], spans: (ReturnType<Composer["snapshot"]>["spans"] | null)[] } | null, visualFrom: number, visualTo: number, visualKind: string, prefix: string, operator: string, digits: string, count: number, counted: boolean, visual: string, anchor: number, find: string, findChar: string, undo: Snapshot[], redo: Snapshot[], base: Snapshot | null, insertBase: Snapshot | null, recipe: Recipe | null, last: Recipe | null, muted: boolean, editFrom: number, editOldTo: number, editNewTo: number, exitCaret: number | null, selectFrom: number, selectTo: number, drawProjection: ReturnType<Composer["_projection"]> | null, drawVisual: string, drawWidth: number, drawScroll: number, drawHeight: number, drawFrom: number, drawTo: number, segments: { row: number, offset: number, value: string }[] }} State */

const MODIFIED = /^(ctrl|alt|super)\+/u;
const DIGIT = /^[1-9]$/u;
const OPERATOR_PREFIX = /^[dcgy<>]/u;
const REGISTER = /^[a-zA-Z0-9"_\-]$/u;
const NUMBERED_DELETE = /^(?:%|n|N|\{|\}|`)/u;
const OBJECT = /^[ia][wW"'`()\[\]{}bB]$/u;
const FIND = /^[fFtT];?$/u;
const OBJECT_PREFIX = /^[ia]/u;
const INDENT = /[ \t]/u;
const INSERT_KEYS = new Set(["i", "a", "I", "A", "o", "O"]);
const CUT_KEYS = new Set(["x", "X", "s", "S", "D", "C", "Y"]);
const VERTICAL = new Set(["j", "k", "up", "down"]);
const NATIVE_MOVES = new Set(["h", "l", "j", "k", "left", "right", "up", "down", "e", "0", "^", "$"]);
const EMPTY_MOTIONS = new Set(["%", "f", "F", "t", "T", "gg", "ge", "gE"]);
const MAX_COUNT = 10000;
const HISTORY_ENTRIES = 100;
const HISTORY_CHARS = 1024 * 1024;

/** Add Vim editing to the profile. This owner keeps per-composer history and shared registers. It returns an active-pane grammar cancel handler. */
export function installVimOperators(/** @type {InjectContext & Pick<import("yuke").Capabilities, "composer-vim">} */ c) {
  /** @type {Readonly<ReturnType<Composer["snapshot"]>["spans"]>} */ const borrowEmptySpans = Object.freeze([]);
  /** @param {ReturnType<Composer["snapshot"]>["spans"][number]} span */
  function copySpan(span) { return { ...span }; }
  const nav = createVimText();
  const edits = createVimEdits(nav);
  /** @type {Map<string, { value: string, lines: boolean }>} */ const registers = new Map();
  const smallDelete = { value: "", lines: false }, zeroYank = { value: "", lines: false };
  const shared = /** @type {typeof c.tui.keymap} */ (Object.getPrototypeOf(c.tui.keymap));
  /** @type {WeakMap<Composer, State>} */ const states = new WeakMap();
  /** @type {WeakMap<Snapshot, Map<string, number>>} */ const snapshotMarks = new WeakMap();
  /** @type {WeakMap<Recipe, string>} */ const ownRecipeRegisters = new WeakMap();
  /** @type {State | null} */ let borrowMarkedState = null;
  let markFrom = 0, markTo = 0, markLength = 0, markText = "", markValue = "";
  /** @param {number} at @param {string} name */
  function shiftMark(at, name) {
    const s = borrowMarkedState;
    if (!s?.marks || at < markFrom) return;
    const row = nav.bounds(markText, at), start = nav.bounds(markText, markFrom);
    if (row.start === start.start && markTo <= row.end && !markValue.includes("\n")) {
      s.marks.set(name, Math.min(at, row.end + markLength - (markTo - markFrom))); return;
    }
    if (!markValue && row.start >= markFrom && row.end < markTo) { s.marks.delete(name); return; }
    s.marks.set(name, at >= markTo ? at + markLength - (markTo - markFrom) : markFrom + Math.min(at - markFrom, markLength));
  }
  /** @param {number} at @param {string} name */
  function restoreMark(at, name) { borrowMarkedState?.marks?.set(name, at); }
  /** @param {State} s @param {number} from @param {number} to @param {string} value @param {string} text */
  function shiftMarks(s, from, to, value, text) {
    borrowMarkedState = s; markFrom = from; markTo = to; markLength = value.length; markText = text; markValue = value;
    try { s.marks?.forEach(shiftMark); } finally { borrowMarkedState = null; markText = ""; markValue = ""; }
  }
  let stored = "", linewise = false, haveRegister = false;
  /** @type {ChatView | null} */ let yankSource = null;
  let yankLinewise = false;

  /** @type {WeakMap<Composer, () => void>} */ const ownClamps = new WeakMap();
  /** @param {Composer} composer */
  function prepareClamp(composer) {
    if (ownClamps.has(composer)) return;
    const release = c.advise(c["composer-vim"], "setMode", "around", (next, target, mode) => {
      if (target !== composer || mode !== "normal") return next(target, mode);
      const at = composer.input.caret;
      release(); ownClamps.delete(composer);
      next(target, mode);
      if (at === 0 && composer.input.text.charCodeAt(0) === 10) composer.input.caret = 0;
    });
    ownClamps.set(composer, release);
  }
  /** @param {Composer} composer @param {State} s */
  function snapshot(composer, s) {
    const owned = { text: composer.input.text, spans: composer.spans.length ? composer.spans.map(copySpan) : borrowEmptySpans, caret: composer.input.caret };
    if (s.marks) snapshotMarks.set(owned, new Map(s.marks));
    return owned;
  }
  /** @param {Composer} composer @returns {State} */
  function stateOf(composer) {
    let state = states.get(composer);
    if (state) return state;
    state = { range: { from: 0, to: 0, target: 0, lines: false }, marks: null, search: null, register: '"', replace: null, visualFrom: 0, visualTo: 0, visualKind: "", prefix: "", operator: "", digits: "", count: 1, counted: false, visual: "", anchor: 0,
      find: "", findChar: "", undo: [], redo: [], base: null, insertBase: null, recipe: null, last: null, muted: false, editFrom: -1, editOldTo: 0, editNewTo: 0, exitCaret: null, selectFrom: 0, selectTo: 0, drawProjection: null, drawVisual: "", drawWidth: -1, drawScroll: -1, drawHeight: -1, drawFrom: -1, drawTo: -1, segments: [] };
    states.set(composer, state);
    const owned = state;
    c.advise(composer.input, "replace", "around", (next, from, to, value) => {
      if (!owned.muted && c["composer-vim"].mode(composer) === "insert" && !owned.base) {
        owned.base = snapshot(composer, owned);
        owned.insertBase = owned.base;
        owned.recipe = recipe("insert", "", "i", 1);
      }
      if (!owned.muted && owned.insertBase && c["composer-vim"].mode(composer) === "insert") {
        if (owned.recipe) {
          if (owned.recipe.edits) owned.recipe.edits.push(from - owned.insertBase.caret, to - from, value);
          else if (owned.editFrom >= 0 && (from > owned.editNewTo || to < owned.editFrom)) owned.recipe.edits = [
            owned.editFrom - owned.insertBase.caret, owned.editOldTo - owned.editFrom, composer.text.slice(owned.editFrom, owned.editNewTo),
            from - owned.insertBase.caret, to - from, value,
          ];
        }
        if (owned.editFrom < 0) { owned.editFrom = from; owned.editOldTo = to; owned.editNewTo = from + value.length; }
        else {
          const delta = owned.editNewTo - owned.editOldTo;
          const originalFrom = from < owned.editFrom ? from : from > owned.editNewTo ? from - delta : owned.editFrom;
          const originalTo = to < owned.editFrom ? to : to > owned.editNewTo ? to - delta : owned.editOldTo;
          owned.editFrom = Math.min(owned.editFrom, originalFrom);
          owned.editOldTo = Math.max(owned.editOldTo, originalTo);
          owned.editNewTo = owned.editOldTo + delta + value.length - (to - from);
        }
      }
      if (owned.marks && !owned.muted) shiftMarks(owned, from, to, value, composer.text);
      return next(from, to, value);
    });
    // A replacement draft or a successful submit starts a new history.
    c.advise(composer.input, "setText", "before", value => {
      if (owned.muted) return;
      owned.undo.length = 0; owned.redo.length = 0;
      owned.base = null; owned.insertBase = null; owned.recipe = null; owned.last = null; owned.editFrom = -1;
      if (value.charCodeAt(0) === 10) prepareClamp(composer);
      owned.marks = null; owned.visualKind = "";
      stopReplace(owned); cancel(owned);
    });
    return state;
  }
  /** @param {string} command @param {string} operator @param {string} motion @param {number} count @param {string} [char] @returns {Recipe} */
  function recipe(command, operator, motion, count, char = "") {
    return { command, operator, motion, count, char, patch: null, size: 0, lines: false, counted: false, edits: null };
  }
  /** @param {State} s */
  function cancel(s) {
    if (s.visual) rememberVisual(s);
    s.register = '"'; s.prefix = ""; s.operator = ""; s.digits = ""; s.count = 1; s.counted = false; s.visual = ""; s.drawProjection = null; s.segments.length = 0;
    if (shared.pending?.kind === "operator" && (OPERATOR_PREFIX.test(shared.pending.stroke) || shared.pending.stroke === "ctrl+r")) shared.pending = null;
  }
  /** @param {Snapshot[]} history @param {Snapshot} value */
  function push(history, value) {
    history.push(value);
    let chars = 0;
    for (let n = history.length - 1; n >= 0; n--) {
      chars += history[n].text.length;
      if (history.length - n > HISTORY_ENTRIES || (chars > HISTORY_CHARS && n < history.length - 1)) { history.splice(0, n + 1); break; }
    }
  }
  /** @param {Composer} composer @param {State} s */
  function capturePatch(composer, s) {
    if (s.insertBase && s.recipe && !s.recipe.edits && !s.recipe.patch) s.recipe.patch = s.editFrom < 0 ? { offset: 0, remove: 0, text: "" } : {
      offset: s.editFrom - s.insertBase.caret, remove: s.editOldTo - s.editFrom, text: composer.text.slice(s.editFrom, s.recipe.motion === "R" && s.replace ? Math.min(s.editNewTo, s.replace.to) : s.editNewTo),
    };
  }
  /** @param {Composer} composer @param {Recipe} action */
  function applyInsert(composer, action) {
    const input = composer.input, origin = input.caret;
    if (action.edits) {
      for (let n = 0; n < action.edits.length; n += 3) {
        const at = Math.max(0, Math.min(input.text.length, origin + /** @type {number} */ (action.edits[n])));
        input.replace(at, Math.min(input.text.length, at + /** @type {number} */ (action.edits[n + 1])), /** @type {string} */ (action.edits[n + 2]));
      }
    } else if (action.patch) {
      const at = Math.max(0, Math.min(input.text.length, origin + action.patch.offset));
      input.replace(at, Math.min(input.text.length, at + action.patch.remove), action.patch.text);
    }
  }
  /** @param {Composer} composer @param {State} s */
  function finish(composer, s) {
    if (!s.base) return;
    capturePatch(composer, s);
    if (s.base.text !== composer.text || s.base.spans.length !== composer.spans.length || s.base.spans.some((span, n) => {
      const live = composer.spans[n];
      return !live || span.start !== live.start || span.end !== live.end || ("blob" in span ? !("blob" in live) || span.blob !== live.blob : "blob" in live);
    })) {
      push(s.undo, s.base); s.redo.length = 0;
      if (s.insertBase && composer.hasImages()) {
        s.last = null;
        c.interaction.notify("Vim repeat is not available for insert changes in a draft with images", "info");
      } else if (s.recipe) s.last = s.recipe;
    }
    s.base = null; s.insertBase = null; s.recipe = null; s.editFrom = -1;
  }
  /** @param {Composer} composer @param {State} s @param {Recipe} action */
  function begin(composer, s, action) {
    finish(composer, s);
    s.base = snapshot(composer, s); s.recipe = action;
  }
  /** @param {Composer} composer @param {State} s @param {Snapshot} snap */
  function restore(composer, s, snap) {
    if (s.marks) {
      const text = composer.text;
      let from = 0, oldTo = text.length, newTo = snap.text.length;
      while (from < oldTo && from < newTo && text[from] === snap.text[from]) from++;
      while (oldTo > from && newTo > from && text[oldTo - 1] === snap.text[newTo - 1]) { oldTo--; newTo--; }
      shiftMarks(s, from, oldTo, snap.text.slice(from, newTo), text);
      const known = snapshotMarks.get(snap);
      if (known) { borrowMarkedState = s; try { known.forEach(restoreMark); } finally { borrowMarkedState = null; } }
    }
    s.muted = true;
    try {
      composer.input.replace(0, composer.text.length, snap.text);
      composer.spans = snap.spans.map(copySpan);
      composer.input.caret = nav.clamp(snap.text, snap.caret);
      composer._invalidate();
    } finally { s.muted = false; }
  }
  /** @param {Composer} composer @param {State} s @param {boolean} redo @param {number} count */
  function history(composer, s, redo, count) {
    finish(composer, s);
    const source = redo ? s.redo : s.undo, target = redo ? s.undo : s.redo;
    for (let n = 0; n < count && source.length; n++) {
      push(target, snapshot(composer, s));
      restore(composer, s, /** @type {Snapshot} */ (source.pop()));
    }
  }
  /** @param {string} value @param {boolean} lines @param {string} [operator] @param {string} [name] @param {string} [motion] */
  function save(value, lines, operator = "y", name = '"', motion = "") {
    if (name === "_") return;
    if (name === '"' && operator === "y") {
      zeroYank.value = value; zeroYank.lines = lines; registers.set("0", zeroYank);
      stored = value; linewise = lines; haveRegister = true; return;
    }
    if (name === '"' && !lines && !value.includes("\n") && !NUMBERED_DELETE.test(motion)) {
      smallDelete.value = value; registers.set("-", smallDelete);
      stored = value; linewise = false; haveRegister = true; return;
    }
    saveRegister(value, lines, operator, name, motion);
  }
  /** @param {string} value @param {boolean} lines @param {string} operator @param {string} name @param {string} motion */
  function saveRegister(value, lines, operator, name, motion) {
    const entry = { value, lines };
    if (operator !== "y") {
      const numbered = lines || value.includes("\n") || NUMBERED_DELETE.test(motion);
      if (numbered) {
        for (let n = 9; n > 1; n--) {
          const previous = registers.get(String(n - 1));
          if (previous) registers.set(String(n), previous); else registers.delete(String(n));
        }
        registers.set("1", entry);
      }
      if (!lines && !value.includes("\n") && name === '"') registers.set("-", entry);
    }
    if (name !== '"') {
      const lower = name.toLowerCase(), previous = registers.get(lower);
      if (name !== lower && previous) {
        entry.value = previous.value + (previous.lines || lines ? "\n" : "") + value;
        entry.lines = previous.lines || lines;
      }
      registers.set(lower, entry);
    }
    stored = entry.value; linewise = entry.lines; haveRegister = true;
  }
  /** @param {State} s */
  function rememberVisual(s) { s.visualFrom = s.selectFrom; s.visualTo = s.selectTo; s.visualKind = s.visual; }
  /** @param {State} s */
  function stopReplace(s) {
    if (s.replace) { s.replace.off?.(); s.replace = null; }
  }

  // Native transcript yanks emit the bytes. No plugin code reads or writes the desktop clipboard.
  c.on("clipboard.copied", ev => {
    if (yankSource === c.tui.root.active && yankSource?.focus === "transcript") {
      const state = states.get(yankSource.composer);
      save(ev.text, yankLinewise, "y", state?.register ?? '"');
      if (state) state.register = '"';
    }
    yankSource = null;
  });
  c.on("key.pressed", ev => {
    if (ev.event === "release") return;
    yankSource = null;
    if ((ev.mods & ~1) !== 0 || ev.code !== "char" || (ev.char !== "y" && ev.char !== "Y")) return;
    const view = c.tui.root.active;
    if (!(view instanceof ChatView) || view.focus !== "transcript" || c.tui.root.focused !== c.tui.root.active) return;
    if (states.get(view.composer)?.prefix === '"') return;
    const pending = shared.pending?.stroke;
    if (ev.char === "y" && pending !== "g" && pending !== "y" && shared.candidates("y").length === 0) return;
    yankSource = view; yankLinewise = ev.char === "Y" || shared.candidates("y").length === 0;
  });

  /** @param {string} text @param {number} caret @param {number} count */
  function lineRange(text, caret, count) {
    const from = nav.bounds(text, caret).start;
    let to = nav.bounds(text, caret).end;
    for (let n = 1; n < count && to < text.length; n++) to = nav.bounds(text, to + 1).end;
    return { from, to };
  }
  /** Borrow the state range until the next motion. @param {Composer} composer @param {State} s @param {string} motion @param {number} count @param {string} char @param {boolean} operator @param {boolean} counted */
  function motionRange(composer, s, motion, count, char, operator, counted = false) {
    const text = composer.text, caret = composer.input.caret, borrowedRange = s.range;
    const bounds = nav.bounds(text, caret);
    let target = caret, inclusive = false, lines = false;
    if (OBJECT.test(motion)) {
      const found = nav.object(text, caret, motion, count);
      if (!found) return null;
      borrowedRange.from = found.from; borrowedRange.to = found.to; borrowedRange.target = found.from; borrowedRange.lines = false;
      return borrowedRange;
    }
    if (motion === "'" || motion === "`") {
      const marked = s.marks?.get(char);
      if (marked == null) return null;
      target = align(text, marked);
      if (motion === "'") {
        const row = nav.bounds(text, target); target = row.start;
        while (target < row.end && INDENT.test(text[target])) target++;
        lines = operator;
      }
    } else if (motion === "n" || motion === "N" || motion === "*" || motion === "#" || motion === "g*" || motion === "g#") {
      const origin = motion !== "n" && motion !== "N" ? setWordSearch(composer, s, motion) : caret;
      if (origin == null || !s.search) return null;
      const found = searchTarget(text, origin, s.search, motion === "N" ? !s.search.forward : s.search.forward, count);
      if (found == null) return null;
      target = found;
    } else if (FIND.test(motion)) {
      const found = nav.find(text, caret, motion[0], char, count, motion.endsWith(";"));
      if (found === null) return null;
      target = found; inclusive = motion[0] === "f" || motion[0] === "t";
    } else if (motion === "%") {
      if (counted) {
        if (count > 100) return null;
        const rowNumber = Math.max(1, Math.ceil(text.split("\n").length * count / 100));
        target = 0;
        for (let n = 1; n < rowNumber; n++) target = nav.bounds(text, target).end + 1;
        const row = nav.bounds(text, target);
        while (target < row.end && (text[target] === " " || text[target] === "\t")) target++;
        lines = operator;
      } else {
        const found = nav.match(text, caret);
        if (found === null) return null;
        target = found; inclusive = true;
      }
    } else if (motion === "gg" || motion === "G") {
      if (counted) {
        target = 0;
        for (let n = 1; n < count && target < text.length; n++) { const row = nav.bounds(text, target); target = row.end < text.length ? row.end + 1 : row.start; if (row.end === text.length) break; }
      } else target = motion === "gg" ? 0 : nav.bounds(text, text.length).start;
      const row = nav.bounds(text, target);
      while (target < row.end && (text[target] === " " || text[target] === "\t")) target++;
      lines = operator;
    } else if (motion === "j" || motion === "k" || motion === "down" || motion === "up") {
      if (!operator) { composer.moveRow((motion === "j" || motion === "down" ? 1 : -1) * count); target = nav.clamp(text, composer.input.caret); }
      else {
        const forward = motion === "j" || motion === "down";
        for (let n = 0; n < count; n++) {
          const row = nav.bounds(text, target);
          if (forward && row.end < text.length) target = row.end + 1;
          else if (!forward && row.start > 0) target = nav.bounds(text, row.start - 1).start;
        }
        lines = true;
      }
    } else if (motion === "$" || motion === "0" || motion === "^") {
      if (motion === "$" && count > 1) target = lineRange(text, caret, count).to;
      else target = motion === "$" ? bounds.end : bounds.start;
      if (motion === "^") while (target < bounds.end && (text[target] === " " || text[target] === "\t")) target++;
      if (motion === "$") { target = nav.clamp(text, target); inclusive = target < text.length && text[target] !== "\n"; }
    } else {
      for (let n = 0; n < count; n++) {
        const before = target;
        switch (motion) {
          case "h": case "left": target = Math.max(bounds.start, nav.step(text, target, false)); break;
          case "l": case "right": target = Math.min(bounds.end, nav.step(text, target, true)); break;
          case "w": case "W": target = nav.wordStart(text, target, motion === "W"); break;
          case "b": case "B": target = nav.wordBack(text, target, motion === "B"); break;
          case "e": case "E": target = nav.step(text, nav.wordEnd(text, target, motion === "E"), false); inclusive = true; break;
          case "ge": case "gE": target = nav.previousEnd(text, target, motion === "gE"); inclusive = true; break;
          case "{": case "}": target = nav.paragraph(text, target, motion === "}"); break;
          default: return null;
        }
        if (target === before) break;
      }
      // A final forward word deletion leaves the line break in place.
      if (operator && (motion === "w" || motion === "W") && target > caret) {
        let previous = nav.step(text, target, false);
        while (previous > caret && nav.cls(text, previous) === 0 && !(text[previous] === "\n" && nav.bounds(text, previous).start === previous)) previous = nav.step(text, previous, false);
        target = Math.min(target, nav.bounds(text, previous).end);
      }
    }
    let from = Math.min(caret, target), to = Math.max(caret, target);
    if (operator && !inclusive && !lines && to > from && text[to - 1] === "\n" && motion === "`") {
      const row = nav.bounds(text, from);
      let first = row.start;
      while (first < row.end && INDENT.test(text[first])) first++;
      if (from <= first) lines = true; else to--;
    }
    if (inclusive) to = nav.step(text, to, true);
    if (lines) { from = nav.bounds(text, from).start; to = nav.bounds(text, to).end; }
    borrowedRange.from = from; borrowedRange.to = to; borrowedRange.target = target; borrowedRange.lines = lines;
    return borrowedRange;
  }
  /** @param {Composer} composer @param {State} s @param {Recipe} action @param {boolean} counted */
  function operate(composer, s, action, counted = false) {
    action.counted = counted;
    if (s.register !== '"') ownRecipeRegisters.set(action, s.register);
    const input = composer.input, text = input.text;
    let range;
    if (action.motion === action.operator || (action.operator[0] === "g" && action.motion === action.operator[1])) {
      const rows = lineRange(text, input.caret, action.count);
      range = { ...rows, target: rows.from, lines: true };
    } else if (action.operator === "c" && (action.motion === "w" || action.motion === "W") && nav.cls(text, input.caret, action.motion === "W") !== 0) {
      let to = input.caret;
      for (let n = 0; n < action.count; n++) to = nav.wordEnd(text, to, action.motion === "W", false);
      range = { from: input.caret, to, target: input.caret, lines: false };
    } else if (action.command === "visual") {
      const from = input.caret;
      const rows = lineRange(text, from, action.size);
      let to = from;
      if (action.lines) to = rows.to;
      else for (let n = 0; n < action.size; n++) to = nav.step(text, to, true);
      range = { from: action.lines ? rows.from : from, to, target: from, lines: action.lines };
    } else range = motionRange(composer, s, action.motion, action.count, action.char, true, counted);
    if (!range) return;
    let { from, to } = range;
    const body = text.slice(from, to);
    if (from === to && !range.lines && action.operator !== "c") return;
    if (action.operator === "y" || action.operator === "d" || action.operator === "c") {
      save(body, range.lines, action.operator, s.register, action.motion);
      if (action.operator === "y") { input.caret = range.lines ? nav.clamp(text, from) : input.caret; return; }
    } else {
      if (action.operator === ">" || action.operator === "<") {
        from = nav.bounds(text, from).start; to = nav.bounds(text, Math.max(from, to - 1)).end;
      }
      const value = action.operator === ">" || action.operator === "<"
        ? edits.shift(text.slice(from, to), action.operator === ">", action.command === "visual" ? action.count : 1)
        : edits.changeCase(body, action.operator);
      if (action.command === "visual" && (action.operator === ">" || action.operator === "<")) {
        action.lines = true; action.size = text.slice(from, to).split("\n").length;
      }
      if (value !== text.slice(from, to)) {
        begin(composer, s, action); input.replace(from, to, value);
      }
      input.caret = nav.clamp(input.text, action.command === "toggle" ? from + value.length : from);
      if (range.lines || action.operator === ">" || action.operator === "<") {
        const row = nav.bounds(input.text, input.caret);
        while (input.caret < row.end && INDENT.test(input.text[input.caret])) input.caret++;
      }
      input.caret = nav.clamp(input.text, input.caret);
      composer.goalCol = null; finish(composer, s); return;
    }
    begin(composer, s, action);
    if (range.lines && action.operator === "d") {
      if (to < text.length) to++;
      else if (from > 0) from--;
    }
    input.replace(from, to, "");
    input.caret = action.operator === "c" ? from : nav.clamp(input.text, from);
    composer.goalCol = null;
    if (action.operator === "c") c["composer-vim"].setMode(composer, "insert");
    else finish(composer, s);
  }
  /** @param {Composer} composer @param {State} s @param {Recipe} action */
  function put(composer, s, action) {
    if (s.register !== '"') ownRecipeRegisters.set(action, s.register);
    const selected = s.register === '"' ? null : registers.get(s.register.toLowerCase());
    if (s.register !== '"' && !selected) return true;
    if (!selected && !haveRegister) return false;
    const valueStored = selected ? selected.value : stored, valueLines = selected ? selected.lines : linewise;
    if (!valueStored && !valueLines) return true;
    if (action.command === "visual-put") { visualPut(composer, s, action, valueStored, valueLines); return true; }
    begin(composer, s, action);
    const input = composer.input, after = action.motion === "p";
    const row = nav.bounds(input.text, input.caret);
    const body = valueStored + (valueLines ? "\n" : "");
    if (valueLines) {
      const at = after ? row.end : row.start;
      const value = after ? "\n" + Array(action.count).fill(valueStored).join("\n") : body.repeat(action.count);
      input.replace(at, at, value); input.caret = at + (after ? 1 : 0);
    } else {
      const at = after ? Math.min(row.end, nav.step(input.text, input.caret, true)) : input.caret;
      const value = body.repeat(action.count);
      input.replace(at, at, value); input.caret = nav.step(input.text, at + value.length, false);
    }
    composer.goalCol = null; finish(composer, s);
    if (selected) { stored = selected.value; linewise = selected.lines; haveRegister = true; }
    return true;
  }
  /** @param {Composer} composer @param {State} s @param {Recipe} action */
  function insert(composer, s, action) {
    begin(composer, s, action);
    const input = composer.input, row = nav.bounds(input.text, input.caret);
    if (action.motion === "a") input.caret = Math.min(row.end, nav.step(input.text, input.caret, true));
    else if (action.motion === "A") input.caret = row.end;
    else if (action.motion === "I") { input.caret = row.start; while (input.caret < row.end && INDENT.test(input.text[input.caret])) input.caret++; }
    else if (action.motion === "o" || action.motion === "O") {
      const at = action.motion === "o" ? row.end : row.start;
      input.replace(at, at, "\n"); input.caret = at + (action.motion === "o" ? 1 : 0);
    }
    c["composer-vim"].setMode(composer, "insert");
    if (action.motion === "R") {
      s.replace = { to: input.caret, off: null, edits: [], spans: [] };
      s.replace.off = c.advise(composer, "onKey", "around", (next, ev) => replaceKey(composer, s, ev) || next(ev));
    }
  }
  /** @param {Composer} composer @param {State} s @param {Parameters<Composer["onKey"]>[0]} ev */
  function replaceKey(composer, s, ev) {
    const replace = s.replace;
    if (!replace || ev.type !== "key" || ev.event === "release") return false;
    const stroke = keys.strokeOf(ev), input = composer.input;
    if (stroke === "backspace") {
      const end = replace.edits.length;
      if (!end) return true;
      const from = /** @type {number} */ (replace.edits[end - 3]), old = /** @type {string} */ (replace.edits[end - 2]), value = /** @type {string} */ (replace.edits[end - 1]);
      if (input.caret !== from + value.length) { replace.edits.length = 0; replace.spans.length = 0; return true; }
      input.replace(from, input.caret, old); input.caret = from;
      const spans = replace.spans.pop();
      if (spans) { composer.spans = spans; composer._invalidate(); }
      replace.edits.length -= 3; replace.to = from; return true;
    }
    if (ev.code !== "char" || (ev.mods & ~1) !== 0) {
      if (stroke !== "esc") { replace.edits.length = 0; replace.spans.length = 0; }
      return false;
    }
    const value = ev.text || ev.char;
    if (!value) return false;
    const from = input.caret, row = nav.bounds(input.text, from);
    let to = from;
    for (let at = 0; at < value.length; at = nav.step(value, at, true)) if (to < row.end) to = nav.step(input.text, to, true);
    replace.edits.push(from, input.text.slice(from, to), value);
    replace.spans.push(composer.spans.length ? composer.snapshot().spans : null);
    input.replace(from, to, value); replace.to = input.caret; return true;
  }
  /** @param {Composer} composer @param {State} s @param {Recipe} action */
  function applyReplacement(composer, s, action) {
    if (!action.patch || action.edits) { applyInsert(composer, action); return; }
    const input = composer.input, rows = action.patch.text.split("\n");
    input.caret = Math.max(0, Math.min(input.text.length, input.caret + action.patch.offset));
    for (let n = 0; n < rows.length; n++) {
      const from = input.caret, row = nav.bounds(input.text, from);
      let to = from;
      for (let at = 0; at < rows[n].length && to < row.end; at = nav.step(rows[n], at, true)) to = nav.step(input.text, to, true);
      input.replace(from, to, rows[n]);
      if (n + 1 < rows.length) input.insert("\n");
    }
    if (s.replace) s.replace.to = input.caret;
  }
  /** @param {Composer} composer @param {State} s @param {Recipe} action */
  function simpleEdit(composer, s, action) {
    if (action.command === "visual-replace") {
      const input = composer.input;
      let from = input.caret, to = from;
      if (action.lines) { const range = lineRange(composer.text, from, action.size); from = range.from; to = range.to; }
      else for (let n = 0; n < action.size; n++) to = nav.step(composer.text, to, true);
      const rows = composer.text.slice(from, to).split("\n");
      for (let n = 0; n < rows.length; n++) rows[n] = action.char.repeat(glyphCount(rows[n]));
      begin(composer, s, action); input.replace(from, to, rows.join("\n"));
      input.caret = nav.clamp(input.text, from); composer.goalCol = null; finish(composer, s); return;
    }
    const plan = action.command === "replace" ? edits.replace(composer.text, composer.input.caret, action.char, action.count)
      : edits.join(composer.text, composer.input.caret, action.count, action.motion === "gJ");
    if (!plan) return;
    begin(composer, s, action);
    composer.input.replace(plan.from, plan.to, plan.value);
    composer.input.caret = nav.clamp(composer.text, plan.caret);
    composer.goalCol = null; finish(composer, s);
  }
  /** @param {Composer} composer @param {State} s @param {number} count @param {boolean} counted */
  function repeat(composer, s, count, counted) {
    const last = s.last;
    if (!last) return;
    if (s.register === '"') s.register = ownRecipeRegisters.get(last) ?? '"';
    const action = { ...last, patch: null, edits: null, count: counted ? count : last.count };
    if (action.command === "put" || action.command === "visual-put") { put(composer, s, action); return; }
    if (action.command === "replace" || action.command === "visual-replace" || action.command === "join") { simpleEdit(composer, s, action); return; }
    if (action.command === "insert") insert(composer, s, action);
    else operate(composer, s, action, counted || last.counted);
    if ((last.patch || last.edits) && c["composer-vim"].mode(composer) === "insert") {
      if (last.motion === "R") applyReplacement(composer, s, last); else applyInsert(composer, last);
      s.exitCaret = composer.input.caret;
      c["composer-vim"].setMode(composer, "normal");
    }
  }
  /** @param {Composer} composer @param {State} s */
  function visualRange(composer, s) {
    const caret = composer.input.caret;
    let from = Math.min(s.anchor, caret), to = nav.step(composer.text, Math.max(s.anchor, caret), true);
    if (s.visual === "line") { from = nav.bounds(composer.text, from).start; to = nav.bounds(composer.text, Math.max(s.anchor, caret)).end; }
    return { from, to };
  }
  /** @param {Composer} composer @param {State} s @param {string} operator @param {number} [count] */
  function visualOperate(composer, s, operator, count = 1) {
    const range = visualRange(composer, s), lines = s.visual === "line";
    const selected = composer.text.slice(range.from, range.to);
    let size = 0;
    if (lines) size = selected.split("\n").length;
    else for (let at = range.from; at < range.to; at = nav.step(composer.text, at, true)) size++;
    rememberVisual(s); composer.input.caret = range.from; s.visual = "";
    const action = recipe("visual", operator, "", count); action.size = size; action.lines = lines;
    operate(composer, s, action);
  }

  /** @param {string} text @param {number} at */
  function align(text, at) {
    at = nav.clamp(text, at);
    const previous = nav.step(text, at, false);
    return nav.step(text, previous, true) > at ? previous : at;
  }
  /** @param {Composer} composer @param {State} s @param {string} motion */
  function setWordSearch(composer, s, motion) {
    const text = composer.text, row = nav.bounds(text, composer.input.caret);
    let at = composer.input.caret;
    while (at < row.end && nav.cls(text, at) !== 1) at = nav.step(text, at, true);
    if (at === row.end) { at = composer.input.caret; while (at < row.end && nav.cls(text, at) === 0) at = nav.step(text, at, true); }
    const range = at < row.end ? nav.object(text, at, "iw", 1) : null;
    if (!range) return null;
    s.search = { value: text.slice(range.from, range.to), forward: motion.endsWith("*"), whole: motion[0] !== "g" && nav.cls(text, at) === 1 };
    return range.from;
  }
  /** @param {string} text @param {number} caret @param {NonNullable<State["search"]>} search @param {boolean} forward @param {number} count */
  function searchTarget(text, caret, search, forward, count) {
    if (!search.value || !text) return null;
    let target = caret;
    for (let n = 0; n < count; n++) {
      let at = target, wrapped = false;
      for (;;) {
        at = forward ? text.indexOf(search.value, at + 1) : at > 0 ? text.lastIndexOf(search.value, at - 1) : -1;
        if (at < 0) {
          if (wrapped) return null;
          wrapped = true; at = forward ? text.indexOf(search.value) : text.lastIndexOf(search.value);
          if (at < 0) return null;
        }
        if (wrapped && (forward ? at > target : at < target)) return null;
        const end = at + search.value.length;
        if (align(text, at) !== at || (search.whole && ((at > 0 && nav.cls(text, nav.step(text, at, false)) === 1) || (end < text.length && nav.cls(text, end) === 1)))) continue;
        target = at; break;
      }
    }
    return target;
  }

  /** @param {State} s @param {string} operator */
  function arm(s, operator) {
    s.operator = operator; s.count = Number(s.digits) || 1; s.counted = s.digits !== ""; s.digits = "";
    shared.pending = { stroke: operator, kind: "operator", at: 0, ev: null };
  }
  /** @param {string} text */
  function glyphCount(text) {
    let count = 0;
    for (let at = 0; at < text.length; at = nav.step(text, at, true)) count++;
    return count;
  }
  /** @param {Composer} composer @param {State} s @param {string} motion */
  function joinCommand(composer, s, motion) {
    let count = Number(s.digits) || 1;
    if (s.visual) {
      const range = visualRange(composer, s);
      count = composer.text.slice(nav.bounds(composer.text, range.from).start, range.to).split("\n").length;
      rememberVisual(s); composer.input.caret = range.from; s.visual = "";
    }
    simpleEdit(composer, s, recipe("join", "", motion, count)); cancelGrammar(s);
  }
  /** @param {Composer} composer @param {State} s @param {Recipe} action @param {string} storedValue @param {boolean} storedLines */
  function visualPut(composer, s, action, storedValue, storedLines) {
    const input = composer.input, text = input.text;
    let from = input.caret, to = from;
    if (action.lines) { const range = lineRange(text, from, action.size); from = range.from; to = range.to; }
    else for (let n = 0; n < action.size; n++) to = nav.step(text, to, true);
    const removed = text.slice(from, to);
    let value = (storedValue + (storedLines ? "\n" : "")).repeat(action.count);
    if (action.lines) {
      if (!storedLines) value += "\n";
      if (to < text.length) to++; else value = value.slice(0, -1);
    } else if (storedLines) {
      value = "\n" + value;
    }
    begin(composer, s, action); input.replace(from, to, value);
    input.caret = nav.clamp(input.text, storedLines ? from + (action.lines ? 0 : 1) : action.lines ? from : nav.step(input.text, from + value.length, false));
    if (action.motion === "p") save(removed, action.lines, "d");
    composer.goalCol = null; finish(composer, s);
  }

  /** Handle a pending prefix on its rare path. Null leaves a count digit to the main grammar. @param {Composer} composer @param {State} s @param {string} stroke @returns {boolean | null} */
  function handlePrefix(composer, s, stroke) {
    if (s.prefix === "f" || s.prefix === "F" || s.prefix === "t" || s.prefix === "T") {
      if (MODIFIED.test(stroke) || nav.step(stroke, 0, true) !== stroke.length) { cancel(s); return false; }
      const motion = s.prefix;
      s.find = motion; s.findChar = stroke;
      return complete(composer, s, motion, stroke);
    }
    if (s.prefix === "r") {
      const count = Number(s.digits) || 1;
      if (stroke === "enter" || nav.step(stroke, 0, true) === stroke.length) {
        const action = recipe(s.visual ? "visual-replace" : "replace", "", "", count, stroke === "enter" ? s.visual ? "\r" : "\n" : stroke);
        if (s.visual) {
          const range = visualRange(composer, s); action.lines = s.visual === "line";
          action.size = action.lines ? composer.text.slice(range.from, range.to).split("\n").length : glyphCount(composer.text.slice(range.from, range.to));
          rememberVisual(s); composer.input.caret = range.from; s.visual = "";
        }
        simpleEdit(composer, s, action);
      }
      cancelGrammar(s); return true;
    }
    if (s.prefix === "m" || s.prefix === "'" || s.prefix === "`") {
      if (!/^[a-z]$/u.test(stroke)) { cancelGrammar(s); return true; }
      if (s.prefix === "m") {
        if (!s.marks) s.marks = new Map();
        s.marks.set(stroke, composer.input.caret); cancelGrammar(s); return true;
      }
      return complete(composer, s, s.prefix, stroke);
    }
    if (s.prefix === '"') {
      s.register = REGISTER.test(stroke) ? stroke : '"'; s.prefix = ""; return true;
    }
    if (DIGIT.test(stroke) || (stroke === "0" && s.digits !== "")) return null;
    if (s.prefix === "i" || s.prefix === "a") return complete(composer, s, s.prefix + stroke, "");
    if (s.prefix === "g") {
      s.prefix = "";
      if (stroke === "u" || stroke === "U" || stroke === "~") {
        if (s.visual) { visualOperate(composer, s, "g" + stroke); cancel(s); return true; }
        if (!s.operator) { arm(s, "g" + stroke); return true; }
      }
      if (stroke === "J" && !s.operator) { joinCommand(composer, s, "gJ"); return true; }
      if (stroke === "v" && !s.operator && s.visualKind) {
        s.visual = s.visualKind; s.anchor = nav.clamp(composer.text, s.visualFrom);
        composer.input.caret = nav.clamp(composer.text, nav.step(composer.text, Math.min(composer.text.length, s.visualTo), false));
        cancelGrammar(s); return true;
      }
      return complete(composer, s, "g" + stroke, "");
    }
    return null;
  }
  /** @param {Composer} composer @param {State} s @param {string} stroke @returns {boolean} */
  function handle(composer, s, stroke) {
    if (stroke === "esc") { cancel(s); return true; }
    if (stroke === "/" && !/^[fFtTr]$/u.test(s.prefix)) { cancel(s); return false; }
    if (MODIFIED.test(stroke)) {
      if (stroke === "ctrl+r") { history(composer, s, true, Math.min(MAX_COUNT, (Number(s.digits) || 1) * s.count)); cancel(s); return true; }
      cancel(s); return false;
    }
    if (s.register === '"' && !s.prefix && !s.operator && !s.digits && !s.visual) {
      if (NATIVE_MOVES.has(stroke) && composer.input.text.charCodeAt(0) !== 10) return false;
      if (stroke === "w" || stroke === "b") {
        composer.input.caret = nav.clamp(composer.text, stroke === "w" ? nav.wordStart(composer.text, composer.input.caret) : nav.wordBack(composer.text, composer.input.caret));
        composer.goalCol = null; return true;
      }
    }
    if (s.prefix) {
      const handled = handlePrefix(composer, s, stroke);
      if (handled != null) return handled;
    }
    if (DIGIT.test(stroke) || (stroke === "0" && s.digits !== "")) {
      s.digits += stroke;
      if (Number(s.digits) > MAX_COUNT) { cancel(s); c.interaction.notify("Vim count exceeds " + MAX_COUNT, "warn"); }
      return true;
    }
    if (stroke === '"' || stroke === "'" || stroke === "`" || (stroke === "m" && !s.operator && !s.visual)) { s.prefix = stroke; return true; }
    if (stroke === "g" || stroke === "f" || stroke === "F" || stroke === "t" || stroke === "T") { s.prefix = stroke; return true; }
    if ((s.operator || s.visual) && (stroke === "i" || stroke === "a")) { s.prefix = stroke; return true; }
    if (stroke === "d" || stroke === "c" || stroke === "y" || stroke === ">" || stroke === "<") {
      if (s.visual) { visualOperate(composer, s, stroke, Number(s.digits) || 1); cancel(s); return true; }
      if (s.operator) return complete(composer, s, stroke, "");
      arm(s, stroke);
      return true;
    }
    if (stroke === ";" || stroke === ",") {
      if (!s.find) { cancel(s); return true; }
      let motion = s.find;
      if (stroke === ",") motion = ({ f: "F", F: "f", t: "T", T: "t" })[motion] || motion;
      const count = (Number(s.digits) || 1) * s.count;
      const target = nav.find(composer.text, composer.input.caret, motion, s.findChar, count, true);
      if (target === null) { cancel(s); return true; }
      // Till repeat uses the next match, but its operator still starts at the current caret.
      if (s.operator) {
        const action = recipe("operator", s.operator, motion + ";", count, s.findChar);
        operate(composer, s, action, s.counted || s.digits !== "");
      } else composer.input.caret = target;
      cancelGrammar(s); return true;
    }
    const count = Math.min(MAX_COUNT, (Number(s.digits) || 1) * s.count), counted = s.counted || s.digits !== "";
    if (!s.operator) {
      if (stroke === "v" || stroke === "V") {
        const visual = stroke === "V" ? "line" : "char";
        if (!s.visual) s.anchor = composer.input.caret;
        s.visual = s.visual === visual ? "" : visual; cancelGrammar(s); return true;
      }
      if (stroke === "o" && s.visual) { const at = s.anchor; s.anchor = composer.input.caret; composer.input.caret = at; cancelGrammar(s); return true; }
      if (INSERT_KEYS.has(stroke)) { insert(composer, s, recipe("insert", "", stroke, count)); cancelGrammar(s); return true; }
      if (s.visual && (stroke === "u" || stroke === "U" || stroke === "~")) { visualOperate(composer, s, stroke === "~" ? "g~" : "g" + stroke); cancel(s); return true; }
      if (stroke === "r") { s.prefix = stroke; return true; }
      if (stroke === "R") { insert(composer, s, recipe("insert", "", stroke, count)); cancelGrammar(s); return true; }
      if (stroke === "J") { joinCommand(composer, s, stroke); return true; }
      if (stroke === "~") { operate(composer, s, recipe("toggle", "g~", "l", count)); cancelGrammar(s); return true; }
      if (stroke === "u" || stroke === "ctrl+r") { history(composer, s, stroke === "ctrl+r", count); cancel(s); return true; }
      if (stroke === ".") { repeat(composer, s, count, counted); cancelGrammar(s); return true; }
      if (stroke === "p" || stroke === "P") {
        const action = recipe(s.visual ? "visual-put" : "put", "", stroke, count);
        if (s.visual) {
          const range = visualRange(composer, s);
          action.lines = s.visual === "line";
          action.size = action.lines ? composer.text.slice(range.from, range.to).split("\n").length : glyphCount(composer.text.slice(range.from, range.to));
          rememberVisual(s); composer.input.caret = range.from; s.visual = "";
        }
        const done = put(composer, s, action); cancelGrammar(s); return done;
      }
      if (CUT_KEYS.has(stroke)) {
        if (s.visual) visualOperate(composer, s, stroke === "s" || stroke === "S" || stroke === "C" ? "c" : stroke === "Y" ? "y" : "d");
        else operate(composer, s, recipe("operator", stroke === "s" || stroke === "S" || stroke === "C" ? "c" : stroke === "Y" ? "y" : "d", stroke === "D" || stroke === "C" ? "$" : stroke === "X" ? "h" : stroke === "S" ? "c" : stroke === "Y" ? "y" : "l", count), counted);
        cancelGrammar(s); return true;
      }
    }
    return complete(composer, s, stroke, "");
  }
  /** @param {State} s */
  function cancelGrammar(s) {
    s.register = '"'; s.prefix = ""; s.operator = ""; s.digits = ""; s.count = 1; s.counted = false;
    if (shared.pending?.kind === "operator" && (OPERATOR_PREFIX.test(shared.pending.stroke) || shared.pending.stroke === "ctrl+r")) shared.pending = null;
  }
  /** @param {Composer} composer @param {State} s @param {string} motion @param {string} char */
  function complete(composer, s, motion, char) {
    const count = (Number(s.digits) || 1) * s.count, counted = s.counted || s.digits !== "";
    if (count > MAX_COUNT) { cancelGrammar(s); c.interaction.notify("Vim count exceeds " + MAX_COUNT, "warn"); return true; }
    if (s.operator) {
      operate(composer, s, recipe("operator", s.operator, motion, count, char), counted);
      cancelGrammar(s); return true;
    }
    const range = motionRange(composer, s, motion, count, char, false, counted);
    cancelGrammar(s);
    if (!range) return EMPTY_MOTIONS.has(motion) || motion === "n" || motion === "N" || motion === "*" || motion === "#" || motion === "g*" || motion === "g#" || motion === "'" || motion === "`";
    if (s.visual && OBJECT_PREFIX.test(motion)) { s.anchor = range.from; composer.input.caret = nav.step(composer.text, range.to, false); }
    else composer.input.caret = nav.clamp(composer.text, range.target);
    if (!VERTICAL.has(motion)) composer.goalCol = null;
    return true;
  }

  let alive = true;
  c.effect(() => () => { alive = false; });
  c.tui.keymap.add({ "alt+/": () => {
    const view = c.tui.root.active;
    if (!(view instanceof ChatView)) return false;
    const composer = view.composer, s = stateOf(composer);
    cancelGrammar(s);
    c.interaction.input("Search draft (literal, case-sensitive)", s.search?.value ?? "").then(value => {
      if (!alive || value == null || c.tui.root.active !== view || view.focus !== "composer" || c["composer-vim"].mode(composer) !== "normal") return;
      const pattern = value || s.search?.value;
      if (!pattern) return;
      s.search = { value: pattern, forward: true, whole: false };
      complete(composer, s, "n", "");
      if (s.visual) { const range = visualRange(composer, s); s.selectFrom = range.from; s.selectTo = range.to; }
      c.tui.root.invalidate();
    }).catch(error => { if (alive) c.interaction.notify(String(error), "warn"); });
    return true;
  } }, "chat && composer && composer_vim == normal && !overlay");
  installTranscriptWords(c, nav, shared);
  c.advise(shared, "onKey", "around", (next, ev) => {
    if (ev.event === "release" || c.tui.root.focused !== c.tui.root.active) return next(ev);
    const view = c.tui.root.active;
    if (!(view instanceof ChatView)) return next(ev);
    if (view.focus === "transcript") {
      const s = states.get(view.composer), stroke = keys.strokeOf(ev);
      if (s?.prefix === '"') { s.register = REGISTER.test(stroke) ? stroke : '"'; s.prefix = ""; return true; }
      if (stroke === '"' && !shared.pending) { stateOf(view.composer).prefix = stroke; return true; }
      if (stroke === "esc" && s) cancel(s);
      return next(ev);
    }
    if (view.focus !== "composer") return next(ev);
    if (c["composer-vim"].mode(view.composer) !== "normal") {
      if (ev.code === "char" && ev.mods === 4 && ev.char === "r") {
        const s = stateOf(view.composer); s.prefix = "insert-register";
        shared.pending = { stroke: "ctrl+r", kind: "operator", at: 0, ev: null }; return true;
      }
      const pending = states.get(view.composer);
      if (pending?.prefix === "insert-register") {
        const name = keys.strokeOf(ev), entry = name === '"' ? haveRegister ? { value: stored, lines: linewise } : null : registers.get(name.toLowerCase());
        shared.pending = null; pending.prefix = "";
        if (REGISTER.test(name) && entry) view.composer.input.insert(entry.value + (entry.lines ? "\n" : ""));
        return true;
      }
      if (ev.code !== "esc") return next(ev);
      stateOf(view.composer).exitCaret = view.composer.input.caret;
      return next(ev);
    }
    const s = stateOf(view.composer);
    const handled = handle(view.composer, s, keys.strokeOf(ev));
    if (s.visual) { const range = visualRange(view.composer, s); s.selectFrom = range.from; s.selectTo = range.to; }
    return handled || next(ev);
  });
  c.on("composer-vim:mode", (composer, mode) => {
    const s = stateOf(composer);
    if (mode === "insert") {
      if (composer.input.text.charCodeAt(0) === 10) prepareClamp(composer);
      s.visual = ""; s.drawProjection = null; s.segments.length = 0;
      if (!s.base) { s.base = snapshot(composer, s); s.recipe = recipe("insert", "", "i", 1); }
      s.insertBase = snapshot(composer, s); s.editFrom = -1;
    } else {
      capturePatch(composer, s); stopReplace(s);
      if (s.recipe?.command === "insert" && s.recipe.count > 1 && s.editFrom >= 0) {
        composer.input.caret = s.exitCaret ?? composer.input.caret;
        s.muted = true;
        try {
          for (let n = 1; n < s.recipe.count; n++) {
            if (s.recipe.motion === "o" || s.recipe.motion === "O") composer.input.insert("\n");
            if (s.recipe.motion === "R") applyReplacement(composer, s, s.recipe); else applyInsert(composer, s.recipe);
          }
        } finally { s.muted = false; }
        s.exitCaret = composer.input.caret;
      }
      finish(composer, s); cancel(s);
      if (s.exitCaret !== null) {
        const text = composer.input.text;
        composer.input.caret = text.charCodeAt(s.exitCaret - 1) === 10 ? s.exitCaret : nav.step(text, s.exitCaret, false);
      }
      s.exitCaret = null;
    }
  });
  /** @param {import("yuke:ui").ViewLike} view */
  function focusEnd(view) {
    if (!(view instanceof ChatView)) return;
    const s = states.get(view.composer);
    if (s) { finish(view.composer, s); stopReplace(s); cancel(s); }
    yankSource = null;
  }
  c.on("region.focused", view => focusEnd(view));
  c.on("pane.closed", view => {
    if (view instanceof ChatView) { const s = states.get(view.composer); if (s) { stopReplace(s); cancel(s); } }
    if (focusedView === view) focusedView = null;
    yankSource = null;
  });
  let focusedView = c.tui.root.active;
  c.on("pane.focused", view => {
    if (focusedView && focusedView !== view) focusEnd(focusedView);
    focusEnd(view); focusedView = view;
  });
  c.on("mouse.received", () => { const view = c.tui.root.active; if (view instanceof ChatView) cancel(stateOf(view.composer)); yankSource = null; });
  c.on("paste.received", () => { const view = c.tui.root.active; if (view instanceof ChatView) cancel(stateOf(view.composer)); yankSource = null; });
  c.tui.status.add({ side: "right", render: () => {
    const view = c.tui.root.active;
    if (!(view instanceof ChatView) || view.focus !== "composer") return "";
    const s = states.get(view.composer);
    return s ? (s.replace ? "REPLACE " : s.visual === "line" ? "VISUAL LINE " : s.visual ? "VISUAL " : "") + s.operator + s.digits + s.prefix : "";
  } });
  c.tui.style.set({ ProfileVimSelection: { reverse: true } });
  c.advise(Composer.prototype, "draw", "after", function (focused) {
    if (!focused) return;
    const s = states.get(this);
    if (s?.visual) drawSelection(this, s);
  });
  /** @param {Composer} composer @param {State} s */
  function drawSelection(composer, s) {
    const rect = composer.rect;
    if (rect.w <= 0 || rect.h <= 0) return;
    const projection = composer._projection(), width = composer._textWidth(rect.w);
    if (s.drawProjection !== projection || s.drawVisual !== s.visual || s.drawWidth !== width || s.drawScroll !== composer.scroll || s.drawHeight !== rect.h || s.drawFrom !== s.selectFrom || s.drawTo !== s.selectTo) buildSelection(composer, s, projection, width);
    for (let n = 0; n < s.segments.length; n++) {
      const segment = s.segments[n];
      paintText(rect.x + rect.w - width + segment.offset, rect.y + segment.row, segment.value, "ProfileVimSelection");
    }
  }
  /** @param {Composer} composer @param {State} s @param {ReturnType<Composer["_projection"]>} projection @param {number} width */
  function buildSelection(composer, s, projection, width) {
    const projected = projection.text;
    const from = composer._toDisplay(s.selectFrom), to = composer._toDisplay(s.selectTo), rows = composer._rowsAt(width);
    s.segments.length = 0;
    for (let i = 0; i < composer.rect.h && i + composer.scroll < rows.length; i++) {
      const row = rows[i + composer.scroll], lo = Math.max(row.start, from), hi = Math.min(row.end, to);
      if (hi > lo) s.segments.push({ row: i, offset: measure(projected.slice(row.start, lo)), value: projected.slice(lo, hi) });
      else if (s.visual === "line" && row.start === row.end && row.start >= from && row.start <= to) s.segments.push({ row: i, offset: 0, value: " " });
    }
    s.drawProjection = projection; s.drawVisual = s.visual; s.drawWidth = width; s.drawScroll = composer.scroll; s.drawHeight = composer.rect.h;
    s.drawFrom = s.selectFrom; s.drawTo = s.selectTo;
  }
  const view = c.tui.root.active;
  if (view instanceof ChatView) stateOf(view.composer);
  c.effect(() => () => {
    const active = c.tui.root.active;
    if (active instanceof ChatView) { const s = states.get(active.composer); if (s) cancel(s); }
    yankSource = null;
  });
  return () => {
    const active = c.tui.root.active;
    if (active instanceof ChatView) { const s = states.get(active.composer); if (s) cancel(s); }
    yankSource = null;
  };
}
