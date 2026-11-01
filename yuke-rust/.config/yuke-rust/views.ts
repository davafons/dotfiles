import { Markdown, type TextDocument } from "yuke:tui";

/** A Markdown document with one stable section. The document owns its parser and row cache. */
export function markdown(key: string, text: string): TextDocument {
  const source = new Markdown(text);
  return {
    key,
    items: [
      {
        key: "body",
        sections: [{ key: "text", kind: "text", text: source.source(), render: (width) => source.rows(width) }],
      },
    ],
  };
}
