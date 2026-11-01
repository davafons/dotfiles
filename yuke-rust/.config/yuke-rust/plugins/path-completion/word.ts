export interface PathWord {
  readonly from: number;
  readonly to: number;
  readonly directory: string;
  readonly prefix: string;
  readonly quote: string;
}

function directoryWord(text: string, caret: number): PathWord | null {
  let from = 3;
  while (text[from] === " " || text[from] === "\t") from++;
  const first = text[from];
  const quote = first === '"' || first === "'" || first === "`" ? first : "";
  if (quote) from++;
  let to = text.length;
  if (quote && text[to - 1] === quote) to--;
  if (caret < from || caret > to) return null;
  const word = text.slice(from, caret);
  const slash = word.lastIndexOf("/");
  return { from, to, directory: slash < 0 ? "./" : word.slice(0, slash + 1), prefix: word.slice(slash + 1), quote };
}

/** @param {string} text @param {number} caret @returns {PathWord | null} */
export function pathWord(text: string, caret: number): PathWord | null {
  if (text[0] === "/" && text[1] === "c" && text[2] === "d" && (text[3] === " " || text[3] === "\t"))
    return directoryWord(text, caret);
  let from = 0,
    quote = "";
  for (let i = 0; i < caret; i++) {
    const char = text[i] ?? "";
    if (quote) {
      if (char === quote || char === "\n") {
        quote = "";
        from = i + 1;
      }
    } else if (i === from && (char === '"' || char === "'" || char === "`")) {
      quote = char;
      from = i + 1;
    } else if (char === " " || char === "\t" || char === "\n" || char === "(" || char === "=") from = i + 1;
  }
  const word = text.slice(from, caret);
  const slash = word.lastIndexOf("/");
  if (slash < 0 || word.startsWith("//") || word.includes(":")) return null;
  if (word[0] === "/" && slash === 0) return null;
  if (word[0] === "~" && !word.startsWith("~/")) return null;
  let to = caret;
  while (to < text.length) {
    const char = text[to] ?? "";
    if (quote ? char === quote || char === "\n" : " \t\r\n)".includes(char)) break;
    to++;
  }
  return { from, to, directory: word.slice(0, slash + 1), prefix: word.slice(slash + 1), quote };
}
