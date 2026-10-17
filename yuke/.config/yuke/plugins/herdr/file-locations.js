/** @typedef {{ path: string, line?: number, column?: number }} FileLocation */

/** Parse a local reference, never a web URL or an editor command. @param {string} value @returns {FileLocation | null} */
export function fileLocation(value) {
  let path = value.trim();
  if ((path[0] === '"' || path[0] === "'" || path[0] === "`") && path.at(-1) === path[0]) path = path.slice(1, -1);
  const uri = path.startsWith("file://");
  if (uri) {
    path = path.slice(7).replace(/^localhost\//, "/");
    if (!path.startsWith("/")) return null;
  } else if (/^[a-z][a-z\d+.-]*:\/\//i.test(path) || /^(?:mailto|javascript|data|https?):/i.test(path)) return null;
  const position = /(?::([1-9]\d*)(?::([1-9]\d*))?|#L([1-9]\d*)(?:C([1-9]\d*)|-L?[1-9]\d*)?)$/.exec(path);
  let line, column;
  if (position) {
    line = Number(position[1] || position[3]);
    column = position[2] || position[4] ? Number(position[2] || position[4]) : undefined;
    path = path.slice(0, position.index);
    if (!Number.isSafeInteger(line) || (column !== undefined && !Number.isSafeInteger(column))) return null;
  }
  if (uri) {
    try { path = decodeURIComponent(path); } catch { return null; }
  }
  if (!path || /[\x00-\x1f\x7f]/.test(path) || /[?#]/.test(path) && !uri) return null;
  return { path, ...(line ? { line } : {}), ...(column ? { column } : {}) };
}

/** Find a link or file token at an exact source offset, including wrapped Markdown labels. @param {string} source @param {number} offset @returns {FileLocation | null} */
export function fileReferenceAt(source, offset) {
  if (offset < 0 || offset >= source.length) return null;
  const links = /!?\[([^\]\n]+)\]\((<[^>\n]+>|[^\s)]+)(?:\s+"[^"\n]*")?\)/g;
  for (const match of source.matchAll(links)) {
    if (offset < match.index || offset >= match.index + match[0].length) continue;
    if (match[0][0] === "!") return null;
    const target = match[2];
    const value = target.startsWith("<") ? target.slice(1, -1) : target;
    try { return fileLocation(value.startsWith("file://") ? value : decodeURIComponent(value)); } catch { return null; }
  }
  for (const match of source.matchAll(/`([^`\n]+)`/g)) {
    if (offset >= match.index && offset < match.index + match[0].length) return /[/.]/.test(match[1]) ? fileLocation(match[1]) : null;
  }
  for (const match of source.matchAll(/[^\s<>\[\]()`"'|]+/g)) {
    if (offset < match.index || offset >= match.index + match[0].length) continue;
    const value = match[0].replace(/[.,;!?]+$/, "");
    if (offset >= match.index + value.length) return null;
    if (!/[/.]/.test(value)) return null;
    return fileLocation(value);
  }
  return null;
}

/** Resolve a file-tool argument hit from metadata, including clipped filenames. Verb and timing hits keep their fold behavior.
 * @param {ReturnType<import("yuke:chat").Transcript["partsOf"]>[number] | undefined} part
 * @param {import("yuke:chat").PartHit["row"]} row
 * @param {number} column
 * @returns {FileLocation | null}
 */
export function fileToolLocation(part, row, column) {
  if (part?.type !== "tool" || !["read", "edit", "write"].includes(part.name) || !row.header) return null;
  let at = 0;
  const argument = row.segments?.some((segment) => {
    const local = column - at;
    at += segment.text.length;
    return segment.src !== undefined && segment.src > 0 && local >= Math.max(0, segment.text.search(/\S/)) && local < segment.text.length;
  });
  if (!argument) return null;
  let args;
  try { args = JSON.parse(part.arguments); } catch { return null; }
  if (!args || Array.isArray(args) || typeof args.path !== "string" || !args.path || /[\x00-\x1f\x7f]/.test(args.path)) return null;
  const line = part.name === "read" && Number.isSafeInteger(args.start) && args.start > 0 ? args.start : undefined;
  return { path: args.path, ...(line ? { line } : {}) };
}
