//! Grapheme-safe text navigation for the profile Vim layer.
import { TextInput } from "yuke:ui";
const BLANK = /\s/u;
const WORD = /[\p{L}\p{N}_]/u;
const OPEN = "([{", CLOSE = ")]}";

/** Create navigation helpers. The returned owner keeps one scratch input and never edits the user's buffer. */
export function createVimText() {
  const probe = new TextInput();
  const right = /** @type {Parameters<TextInput["onKey"]>[0]} */ ({ type: "key", code: "right", event: "press", char: "", shifted: "", baseLayout: "", text: "", mods: 0 });
  const left = /** @type {Parameters<TextInput["onKey"]>[0]} */ ({ ...right, code: "left" });
  /** @param {string} text @param {number} at @param {boolean} forward */
  function step(text, at, forward) {
    probe.text = text; probe.caret = at;
    probe.onKey(forward ? right : left);
    probe.text = "";
    return probe.caret;
  }
  /** @param {string} text @param {number} at @param {boolean} big */
  function cls(text, at, big = false) {
    const glyph = text.slice(at, step(text, at, true));
    return !glyph || BLANK.test(glyph) ? 0 : big || WORD.test(glyph) ? 1 : 2;
  }
  /** @param {string} text @param {number} at @param {boolean} big */
  function wordStart(text, at, big = false) {
    const origin = at, kind = cls(text, at, big);
    if (kind) while (at < text.length && cls(text, at, big) === kind) at = step(text, at, true);
    while (at < text.length && cls(text, at, big) === 0) {
      if (at > origin && text[at] === "\n" && (at === 0 || text[at - 1] === "\n")) return at;
      at = step(text, at, true);
    }
    return at;
  }
  /** @param {string} text @param {number} at @param {boolean} big */
  function wordBack(text, at, big = false) {
    if (!at) return 0;
    at = step(text, at, false);
    while (at > 0 && cls(text, at, big) === 0) {
      if (text[at] === "\n" && text[at - 1] === "\n") return at;
      at = step(text, at, false);
    }
    const kind = cls(text, at, big);
    while (at > 0) {
      const prev = step(text, at, false);
      if (cls(text, prev, big) !== kind) break;
      at = prev;
    }
    return at;
  }
  /** @param {string} text @param {number} at @param {boolean} big @param {boolean} advance */
  function wordEnd(text, at, big = false, advance = true) {
    if (advance) at = step(text, at, true);
    while (at < text.length && cls(text, at, big) === 0) at = step(text, at, true);
    const kind = cls(text, at, big);
    while (at < text.length) {
      const next = step(text, at, true);
      if (next === text.length || cls(text, next, big) !== kind) return next;
      at = next;
    }
    return text.length;
  }
  /** @param {string} text @param {number} at @param {boolean} big */
  function previousEnd(text, at, big = false) {
    if (!at) return 0;
    const kind = cls(text, at, big);
    let prev = step(text, at, false);
    if (kind && cls(text, prev, big) === kind) {
      while (prev > 0 && cls(text, prev, big) === kind) prev = step(text, prev, false);
      if (prev === 0 && cls(text, prev, big) === kind) return 0;
    }
    while (prev > 0 && cls(text, prev, big) === 0) {
      if (text[prev] === "\n" && text[prev - 1] === "\n") return prev;
      prev = step(text, prev, false);
    }
    return prev;
  }
  /** @param {string} text @param {number} caret */
  function bounds(text, caret) {
    const start = caret === 0 ? 0 : text.lastIndexOf("\n", caret - 1) + 1;
    const stop = text.indexOf("\n", caret);
    return { start, end: stop < 0 ? text.length : stop };
  }
  /** @param {string} text @param {number} caret */
  function clamp(text, caret) {
    caret = Math.max(0, Math.min(text.length, caret));
    const { start, end } = bounds(text, caret);
    return caret === end && end > start ? step(text, end, false) : caret;
  }
  /** @param {string} text @param {number} at */
  function escaped(text, at) {
    let slashes = 0;
    while (at > 0 && text[--at] === "\\") slashes++;
    return slashes % 2 !== 0;
  }
  /** @param {string} text @param {number} at */
  function quoteOpens(text, at) {
    const char = text[at];
    if (char === "'" && at > 0 && WORD.test(text[at - 1])) return false;
    let closing = text.indexOf(char, at + 1);
    while (closing >= 0 && escaped(text, closing)) closing = text.indexOf(char, closing + 1);
    return closing >= 0 && (char === "`" || text.lastIndexOf("\n", closing - 1) < at);
  }
  /** @param {string} text @param {number} caret @param {string} kind @param {number} count */
  function object(text, caret, kind, count) {
    const around = kind[0] === "a", token = kind[1];
    const { start, end } = bounds(text, caret);
    if (token === "w" || token === "W") {
      if (caret === end) return null;
      const big = token === "W", category = cls(text, caret, big);
      let from = caret, to = step(text, caret, true);
      while (from > start) {
        const prev = step(text, from, false);
        if (cls(text, prev, big) !== category) break;
        from = prev;
      }
      while (to < end && cls(text, to, big) === category) to = step(text, to, true);
      for (let n = 1; n < count && to < text.length; n++) {
        let next = to;
        while (next < text.length && cls(text, next, big) === 0) next = step(text, next, true);
        to = wordEnd(text, next, big, false);
      }
      if (around && category === 0) {
        if (to < end) to = Math.min(end, wordEnd(text, to, big, false));
        else if (from > start) from = Math.max(start, wordBack(text, from, big));
      } else if (around) {
        if (to < end && cls(text, to, big) === 0) {
          while (to < end && cls(text, to, big) === 0) to = step(text, to, true);
        } else while (from > start) {
          const prev = step(text, from, false);
          if (cls(text, prev, big) !== 0) break;
          from = prev;
        }
      }
      return { from, to };
    }
    if (token === '"' || token === "'" || token === "`") {
      let opening = -1;
      for (let at = start; at < end; at++) {
        if (text[at] !== token || escaped(text, at)) continue;
        if (opening < 0) { opening = at; continue; }
        if (at >= caret) {
          const closing = at, includeQuotes = around || count > 1;
          let from = opening + (includeQuotes ? 0 : 1), to = closing + (includeQuotes ? 1 : 0);
          if (around) {
            if (to < end && cls(text, to) === 0) while (to < end && cls(text, to) === 0) to = step(text, to, true);
            else while (from > start) { const prev = step(text, from, false); if (cls(text, prev) !== 0) break; from = prev; }
          }
          return { from, to };
        }
        opening = -1;
      }
      return null;
    }
    const index = token === "b" ? 0 : token === "B" ? 2 : Math.max(OPEN.indexOf(token), CLOSE.indexOf(token));
    if (index < 0) return null;
    /** @type {number[]} */ const stack = [];
    /** @type {{ from: number, to: number }[]} */ const enclosing = [];
    let quote = "";
    for (let at = 0; at < text.length; at++) {
      const char = text[at];
      if (escaped(text, at)) continue;
      if (quote) { if (char === quote) quote = ""; continue; }
      if ((char === '"' || char === "'" || char === "`") && quoteOpens(text, at)) { quote = char; continue; }
      if (char === OPEN[index]) stack.push(at);
      else if (char === CLOSE[index] && stack.length) {
        const opening = /** @type {number} */ (stack.pop());
        if (opening <= caret && at >= caret) enclosing.push({ from: opening, to: at });
      }
    }
    const pair = enclosing[count - 1];
    return pair ? { from: pair.from + (around ? 0 : 1), to: pair.to + (around ? 1 : 0) } : null;
  }
  /** @param {string} text @param {number} caret @param {string} motion @param {string} char @param {number} count @param {boolean} repeat */
  function find(text, caret, motion, char, count, repeat = false) {
    const forward = motion === "f" || motion === "t", till = motion === "t" || motion === "T";
    const { start, end } = bounds(text, caret);
    let at = caret;
    // A repeated till starts past the previous match, not beside it again.
    if (repeat && till) at = step(text, at, forward);
    for (let n = 0; n < count; n++) {
      let found = -1;
      while (forward ? at < end : at > start) {
        at = step(text, at, forward);
        if (at >= end) break;
        const glyph = text.slice(at, step(text, at, true));
        if (glyph === char) { found = at; break; }
      }
      if (found < 0) return null;
      at = found;
    }
    return till ? step(text, at, !forward) : at;
  }
  /** @param {string} text @param {number} caret */
  function match(text, caret) {
    const { end } = bounds(text, caret);
    /** @type {{ at: number, index: number }[]} */ const stack = [];
    let quote = "", candidate = -1;
    for (let at = 0; at < text.length; at++) {
      const char = text[at];
      if (escaped(text, at)) continue;
      if (quote) { if (char === quote) quote = ""; continue; }
      if ((char === '"' || char === "'" || char === "`") && quoteOpens(text, at)) { quote = char; continue; }
      const opening = OPEN.indexOf(char), closing = CLOSE.indexOf(char);
      if (opening < 0 && closing < 0) continue;
      if (candidate < 0 && at >= caret && at < end) candidate = at;
      if (opening >= 0) stack.push({ at, index: opening });
      else if (stack.length && stack[stack.length - 1].index === closing) {
        const pair = /** @type {{ at: number, index: number }} */ (stack.pop());
        if (pair.at === candidate) return at;
        if (at === candidate) return pair.at;
      }
      if (at === candidate && closing >= 0) return null;
    }
    return null;
  }
  /** @param {string} text @param {number} caret @param {boolean} forward */
  function paragraph(text, caret, forward) {
    let at = bounds(text, caret).start;
    let crossedText = text.slice(at, bounds(text, at).end).length !== 0;
    while (forward ? at < text.length : at > 0) {
      const row = bounds(text, at);
      if (forward) {
        if (row.end === text.length) return text.length;
        at = row.end + 1;
      } else at = bounds(text, at - 1).start;
      const blank = text.slice(at, bounds(text, at).end).length === 0;
      if (crossedText && blank) return at;
      if (!blank) crossedText = true;
    }
    return at;
  }
  return { step, cls, wordStart, wordBack, wordEnd, previousEnd, bounds, clamp, object, find, match, paragraph };
}
