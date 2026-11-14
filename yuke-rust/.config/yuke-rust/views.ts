import { Markdown, type TextDocument } from "yuke:tui";

/** A Markdown document with one stable section. The document owns its parser and row cache. */
export function markdown(key: string, text: string): TextDocument {
  const source = new Markdown(text);
  return {
    id: key,
    items: [
      {
        id: "body",
        sections: [{ id: "text", kind: "text", text: source.source(), render: (width) => source.rows(width) }],
      },
    ],
  };
}
