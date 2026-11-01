import type { PluginContext } from "yuke:plugins";
import { assert, createFrame, equal, test } from "yuke:test";
import { TextEditor, TextView, type View } from "yuke:tui";
import { apply } from "../src/index.ts";

function reader(text = "alpha beta gamma\n你好 hello\nlast line") {
  const group = {};
  const editor = new TextEditor({ role: "composer", group });
  const view = new TextView({
    role: "transcript",
    group,
    document: {
      key: "chat",
      items: [
        {
          key: "a",
          sections: [
            { key: "body", kind: "text", text },
            {
              key: "tool",
              kind: "label",
              text: "read /a/very/long/source/path.txt",
              render: () => [
                { segments: [{ text: "read /a/…", source: { kind: "elision", from: 0, to: 33 } }], join: "" },
              ],
            },
          ],
        },
      ],
    },
  });
  const root: View = {
    initialFocus: editor,
    layout: (size) => [
      { view, rect: { column: 0, row: 0, width: size.width, height: size.height - 2 } },
      { view: editor, rect: { column: 0, row: size.height - 2, width: size.width, height: 2 } },
    ],
    draw() {},
  };
  const frame = createFrame({ width: 40, height: 10 }, () => root);
  const surface = frame.surface("vim");
  apply({
    get: (name: string) => (name === "tui" ? surface.tui : { session: () => "s" }),
    provide() {},
    notify() {},
    signal: surface.signal,
  } as unknown as PluginContext);
  frame.draw();
  frame.key("esc");
  frame.key("tab");
  assert(surface.tui.focused === view);
  return { frame, view, editor, surface };
}

test("transcript Vim yanks display words and keeps registers available to the composer", () => {
  const { frame, view, editor, surface } = reader();
  using _owned = frame;
  frame.key("g g 0 2 y w");
  equal(frame.copies.at(-1), "alpha beta ");
  equal(view.selection, undefined);
  frame.key("tab");
  assert(surface.tui.focused === editor);
  frame.key("p");
  equal(editor.state.text, "alpha beta ");
});

test("transcript marks keep their source offset after resize and source yanks include an elided title", () => {
  const { frame, view } = reader();
  using _owned = frame;
  frame.key("g g w m a G 0 l l l l l l l");
  equal(view.caret?.offset, 7);
  frame.key("g y");
  equal(frame.copies.at(-1), "read /a/very/long/source/path.txt");
  frame.resize({ width: 12, height: 12 });
  frame.key("` a");
  equal(view.caret, { item: "a", section: "body", offset: 6 });
});

test("transcript visual line yanks span Unicode rows and restore the selection", () => {
  const { frame, view } = reader();
  using _owned = frame;
  frame.key("g g j V j y");
  equal(frame.copies.at(-1), "你好 hello\nlast line");
  frame.key("g v");
  assert(view.selection !== undefined);
  frame.key("esc");
  equal(view.selection, undefined);
});

test("whole-word transcript search skips a longer word and repeats in both directions", () => {
  const { frame, view } = reader("alpha alphabet alpha.\nnext alpha");
  using _owned = frame;
  frame.key("g g *");
  equal(view.caret?.offset, 15);
  frame.key("n");
  equal(view.caret?.offset, 27);
  frame.key("N");
  equal(view.caret?.offset, 15);
  frame.key("g g g *");
  equal(view.caret?.offset, 6);
});

test("a transcript search dialog keeps the source cursor while it owns the focus", () => {
  const { frame, view, surface } = reader();
  using _owned = frame;
  frame.key("g g /");
  frame.paste("gamma");
  frame.key("enter");
  equal(view.caret, { item: "a", section: "body", offset: 11 });
  assert(surface.tui.focused === view);
});

test("Tab returns to the same transcript source position after composer editing", () => {
  const { frame, view, editor } = reader();
  using _owned = frame;
  frame.key("g g w tab i");
  frame.paste("draft stays");
  frame.key("esc tab");
  equal(view.caret, { item: "a", section: "body", offset: 6 });
  equal(editor.state.text, "draft stays");
});
