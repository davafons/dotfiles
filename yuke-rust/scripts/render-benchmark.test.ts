import { env } from "yuke:process";
import { assert, createFrame, equal, test } from "yuke:test";
import { Markdown, TextEditor, TextView } from "yuke:tui";

const iterations = Number(env.get("YUKE_BENCH_ITERATIONS") ?? 300);
assert(Number.isInteger(iterations) && iterations > 0 && iterations <= 1500);

test("measure real transcript frames with scrolling and source mapping", () => {
  const text = "## Captured work\nRead **source** and verify `tests`.\n".repeat(20);
  const markdown = new Markdown(text);
  const view = new TextView({
    document: {
      key: "bench",
      items: Array.from({ length: 120 }, (_, index) => ({
        key: `i${index}`,
        sections: [{ key: "body", kind: "text" as const, text, render: (width: number) => markdown.rows(width) }],
      })),
    },
  });
  using frame = createFrame({ width: 100, height: 30 }, () => view);
  let cells = 0;
  for (let index = 0; index < iterations; index += 1) {
    view.scroll.scrollBy(index % 2 === 0 ? 1 : -1);
    const rendered = frame.draw();
    cells += rendered.cells.length;
    const position = view.rows.at({ column: 12, row: index % 20 });
    assert(position !== undefined);
    assert(view.rows.point(position) !== undefined);
  }
  equal(cells, iterations * 30);
});

test("measure real composer input and redraw", () => {
  const editor = new TextEditor({
    state: { text: "A draft with enough words to wrap. ".repeat(30), selection: { anchor: 0, head: 0 }, spans: [] },
  });
  using frame = createFrame({ width: 100, height: 30 }, () => editor);
  for (let index = 0; index < iterations; index += 1) {
    frame.paste("x");
    frame.key("backspace");
  }
  assert(editor.state.text.startsWith("A draft"));
  equal(editor.state.text.length, "A draft with enough words to wrap. ".repeat(30).length);
});
