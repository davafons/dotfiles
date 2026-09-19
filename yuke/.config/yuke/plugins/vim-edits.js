//! Grapheme-safe replacement, case changes, and logical-line edits.
/** @typedef {ReturnType<typeof import("./vim-text.js").createVimText>} Navigation */

/** Create edit planners. Each result owns its replacement string. Null means that the edit cannot run. */
export function createVimEdits(/** @type {Navigation} */ nav) {
  /** @param {string} text @param {number} at @param {string} glyph @param {number} count */
  function replace(text, at, glyph, count) {
    const row = nav.bounds(text, at);
    let to = at;
    for (let n = 0; n < count; n++) {
      if (to >= row.end) return null;
      to = nav.step(text, to, true);
    }
    const value = glyph === "\n" ? glyph : glyph.repeat(count);
    return { from: at, to, value, caret: glyph === "\n" ? at + 1 : nav.step(value, value.length, false) + at };
  }
  /** @param {string} text @param {number} at @param {number} count @param {boolean} raw */
  function join(text, at, count, raw) {
    const row = nav.bounds(text, at);
    if (row.end === text.length) return null;
    let to = row.end, value = text.slice(row.start, to), caret = row.end;
    for (let n = 1; n < Math.max(2, count) && to < text.length; n++) {
      const next = nav.bounds(text, to + 1);
      let body = text.slice(next.start, next.end);
      if (!raw) body = body.replace(/^[ \t]+/u, "");
      caret = row.start + value.length;
      if (!raw && value && body && !/[ \t]$/u.test(value) && body[0] !== ")") value += " ";
      value += body; to = next.end;
    }
    return { from: row.start, to, value, caret };
  }
  /** @param {string} text @param {string} operator */
  function changeCase(text, operator) {
    if (operator === "gu") return text.toLowerCase();
    if (operator === "gU") return text.toUpperCase();
    let result = "";
    for (let at = 0; at < text.length;) {
      const to = nav.step(text, at, true), glyph = text.slice(at, to), lower = glyph.toLowerCase();
      result += glyph === lower ? glyph.toUpperCase() : lower; at = to;
    }
    return result;
  }
  /** @param {string} text @param {boolean} right @param {number} count */
  function shift(text, right, count) {
    const rows = text.split("\n"), width = count * 2;
    for (let n = 0; n < rows.length; n++) {
      const row = rows[n];
      let at = 0, column = 0;
      while (at < row.length && (row[at] === " " || row[at] === "\t")) {
        column += row[at] === "\t" ? 2 - column % 2 : 1; at++;
      }
      if (!row.length) continue;
      rows[n] = " ".repeat(right ? column + width : Math.max(0, column - width)) + row.slice(at);
    }
    return rows.join("\n");
  }
  return { replace, join, changeCase, shift };
}
