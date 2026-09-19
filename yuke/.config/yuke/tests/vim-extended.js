//! Extended Vim checks through the real root dispatch. No test opens a terminal or accesses the clipboard.
import { plugins } from "yuke";
import { ChatView } from "yuke:chat";
/** @import { Plugin } from "yuke" */
plugins.use(/** @type {Plugin} */ ({
  name: "vim-extended-checks",
  apply(ctx) {
    ctx.inject(["tui", "composer-vim"], c => {
      const active = c.tui.root.active;
      if (!(active instanceof ChatView)) throw Error("missing chat");
      const view = active, input = view.composer.input, mode = c["composer-vim"];
      /** @param {boolean} ok @param {string} message */
      function assert(ok, message) { if (!ok) throw Error(message); }
      /** @param {string} char @param {number} [mods] */
      function key(char, mods = 0) { c.tui.root.onEvent({ type: "key", code: "char", event: "press", char, shifted: "", baseLayout: "", text: mods ? "" : char, mods }); }
      /** @param {string} value */
      function press(value) { for (const char of value) key(char); }
      function esc() { c.tui.root.onEvent({ type: "key", code: "esc", event: "press", char: "", shifted: "", baseLayout: "", text: "", mods: 0 }); }
      /** @param {string} value @param {number} [at] */
      function reset(value, at = 0) { view.focusRegion("composer"); mode.setMode(view.composer, "insert"); input.setText(value); input.caret = at; mode.setMode(view.composer, "normal"); }
      /** @param {string} value @param {number} at @param {string} strokes @param {string} expected @param {number} [caret] */
      function check(value, at, strokes, expected, caret) {
        reset(value, at); press(strokes);
        assert(input.text === expected, strokes + " text: " + JSON.stringify(input.text));
        if (caret !== undefined) assert(input.caret === caret, strokes + " caret: " + input.caret);
      }
      check("one two three four", 0, "3w", "one two three four", 14);
      check("one two three four", 14, "2b", "one two three four", 4);
      check("alpha\n\nbravo charlie", 0, "w", "alpha\n\nbravo charlie", 6);
      check("alpha\n\nbravo charlie", 0, "2w", "alpha\n\nbravo charlie", 7);
      check("alpha\n\nbravo charlie", 7, "b", "alpha\n\nbravo charlie", 6);
      check("alpha\n\nbravo charlie", 7, "ge", "alpha\n\nbravo charlie", 6);
      check("one two three four five", 0, "d2w", "three four five", 0);
      check("one two three four five", 0, "2dw", "three four five", 0);
      check("one two three four five", 0, "2d2w", "five", 0);
      check("a\nb\nc\nd", 0, "3dd", "d", 0);
      check("a\nb\nc\nd", 0, "2G", "a\nb\nc\nd", 2);
      check("a\n  b\nc", 0, "2G", "a\n  b\nc", 4);
      check("a\n  b\nc\nd", 0, "50%", "a\n  b\nc\nd", 4);
      check("a\nb\nc\nd", 6, "2gg", "a\nb\nc\nd", 2);
      check("alpha\n  bravo", 0, "dw", "\n  bravo", 0);
      check("foo,bar", 0, "c2w", "bar", 0);
      assert(mode.mode(view.composer) === "insert", "counted cw enters insert");

      check("a,b,c,d", 0, "f,", "a,b,c,d", 1);
      press(";"); assert(input.caret === 3, "semicolon repeats find");
      press(","); assert(input.caret === 1, "comma reverses find");
      press(";"); assert(input.caret === 3, "reverse does not change the saved find");
      check("a,b,c,d", 0, "2f,", "a,b,c,d", 3);
      check("a,b,c,d", 0, "t,;", "a,b,c,d", 2);
      check("a,b,c,d", 6, "T,", "a,b,c,d", 6);
      press(";"); assert(input.caret === 4, "backward till repeat skips the previous match");
      check("foo(bar)baz", 4, "dt)", "foo()baz", 4);
      check("foo(bar)baz", 4, "df)", "foo(baz", 4);
      check("foo(bar)baz", 6, "dF(", "foor)baz", 3);
      check("foo(bar)baz", 6, "dT(", "foo(r)baz", 4);
      check("abc\ndef", 0, "fz", "abc\ndef", 0);
      check("a+b+c", 0, "f+", "a+b+c", 1);
      check("a👩‍💻b", 0, "f", "a👩‍💻b", 0);
      key("👩‍💻"); assert(input.caret === 1, "find accepts one grapheme");
      check("a,b,c,d", 0, "t,d;", ",c,d", 0);

      check('say "hello" now', 6, 'ci"', 'say "" now', 5);
      press("new"); esc(); assert(input.text === 'say "new" now' && input.caret === 7, "quote change and escape caret");
      check("say 'hello' now", 6, "da'", "say now", 4);
      check('say "hello" now', 6, '2di"', 'say  now', 4);
      check('say "hello" now', 6, '2da"', 'say now', 4);
      check('say "a\\\"b" now', 7, 'di"', 'say "" now', 5);
      check("f(one (two) three)", 8, "di(", "f(one () three)", 7);
      check("f(one (two) three)", 8, "d2i(", "f()", 2);
      check("f(one (two) three)", 8, "da)", "f(one  three)", 6);
      check("a[one]b", 3, "di]", "a[]b", 2);
      check("a{one}b", 3, "ciB", "a{}b", 2);
      check("foo,bar baz", 4, "diW", " baz", 0);
      check("foo,bar baz", 4, "daW", "baz", 0);
      check("plain text", 0, 'di"', "plain text", 0);
      check("foo,bar baz", 0, "E", "foo,bar baz", 6);
      check("alpha bravo", 7, "ge", "alpha bravo", 4);
      check("foo,bar baz", 9, "gE", "foo,bar baz", 6);
      check("alpha bravo", 6, "dge", "alphravo", 4);
      check("a(b[c]d)e", 1, "%", "a(b[c]d)e", 7);
      press("%"); assert(input.caret === 1, "percent reverses the pair jump");
      check("a(b[c]d)e", 1, "d%", "ae", 1);
      check("unmatched (", 10, "%", "unmatched (", 10);
      check('f(")")', 1, "%", 'f(")")', 5);
      check('f("(")', 5, "%", 'f("(")', 1);
      check("(I can't do this)", 0, "%", "(I can't do this)", 16);
      check("(I can't do this)", 4, "di(", "()", 1);
      check("one\ntwo\n\nthree\n\nfour", 0, "}", "one\ntwo\n\nthree\n\nfour", 8);
      press("}"); assert(input.caret === 15, "next paragraph boundary");
      press("{"); assert(input.caret === 8, "previous paragraph boundary");
      check("one\ntwo\n\nthree", 0, "d}", "\nthree", 0);
      check("one\n  \nthree", 0, "}", "one\n  \nthree", 11);

      check("alpha bravo", 0, "vwd", "ravo", 0);
      press("u"); assert(input.text === "alpha bravo", "undo visual delete");
      check("alpha bravo", 2, "viwy", "alpha bravo", 0);
      press("$p"); assert(input.text === "alpha bravoalpha", "visual word yank and put");
      check("a\nb\nc", 0, "Vjd", "c", 0);
      press("u"); assert(input.text === "a\nb\nc", "undo visual line delete");
      check("a\nb\nc", 0, "Vjc", "\nc", 0);
      press("z"); esc(); assert(input.text === "z\nc", "change visual lines");
      check("abc", 0, "vl", "abc", 1);
      esc(); press("x"); assert(input.text === "ac", "escape cancels visual mode");
      check("abc", 0, "vlo", "abc", 0);

      check("alpha bravo charlie", 0, "dw", "bravo charlie", 0);
      press("u"); assert(input.text === "alpha bravo charlie" && input.caret === 0, "undo restores text and caret");
      key("r", 4); assert(input.text === "bravo charlie", "control R redoes");
      press("u"); press("x"); key("r", 4); assert(input.text === "lpha bravo charlie", "new edit clears redo");
      reset("abc"); press("iXYZ"); esc();
      assert(input.text === "XYZabc" && input.caret === 2, "insert escape lands on final inserted glyph");
      press("u"); assert(input.text === "abc", "one undo reverses the full insert group");
      key("r", 4); assert(input.text === "XYZabc", "redo restores insert group");
      reset(""); press("iabc"); esc(); assert(input.caret === 2, "escape at end moves only once");
      press("u"); assert(input.text === "", "undo works for an empty snapshot");
      reset("alpha bravo"); press("ciwXYZ"); esc(); press("u");
      assert(input.text === "alpha bravo", "change plus typed replacement is one undo group");
      check("one two three four", 0, "dw.", "three four", 0);
      press("u"); assert(input.text === "two three four", "dot is one undo group");
      check("one two three four five", 0, "dw2.", "four five", 0);
      reset("alpha bravo charlie"); press("ciwX"); esc(); press("w.");
      assert(input.text === "X X charlie", "dot repeats change plus inserted text");
      reset("a b c"); press("ia"); esc(); press("w.");
      assert(input.text === "aa ab c", "repeat insert does not infer an ambiguous diff");
      reset("alpha bravo"); press("ciwX"); esc();
      c.tui.root.onEvent({ type: "key", code: "right", event: "press", char: "", shifted: "", baseLayout: "", text: "", mods: 0 });
      press("w."); assert(input.text === "X X", "dot survives a cursor move");
      reset("a\nb\nc"); press("ddp"); press("."); assert(input.text === "b\na\na\nc", "dot repeats a linewise put");
      reset("abc def"); press("iX");
      c.tui.root.onEvent({ type: "key", code: "right", event: "press", char: "", shifted: "", baseLayout: "", text: "", mods: 0 });
      press("Y"); esc(); press("w.");
      assert(input.text === "XaYbc XdYef", "dot preserves new text between non-contiguous insert edits");
      reset("abc"); press("3iX"); esc();
      assert(input.text === "XXXabc" && input.caret === 2, "counted insertion repeats one unit");
      press("u"); assert(input.text === "abc", "counted insertion is one undo group");
      key("r", 4); press("w.");
      assert(input.text === "XXXabXXXc", "dot retains counted insertion count");
      reset("a"); press("oX"); esc(); press(".");
      assert(input.text === "a\nX\nX", "dot repeats open-line insertion");
      reset("a"); press("3oX"); esc();
      assert(input.text === "a\nX\nX\nX", "counted open lines keep line separators");
      check("abc", 0, "vlld.", "", 0);
      check("one two", 0, "dw", "two");
      view.composer.spans = [{ start: 0, end: 3 }];
      press("x"); press("u"); assert(view.composer.spans.length === 1 && view.composer.spans[0].end === 3, "undo restores collapsed spans");
      view.composer.spans = [];
      reset("draft"); press("iIMG");
      // Metadata stays in the composer. This check never reads an image from the engine store.
      const blob = { hash: "0".repeat(64), mime: "image/png", bytes: 0 };
      view.composer.spans = [{ start: 0, end: 3, blob }];
      esc(); press("."); assert(input.text === "IMGdraft", "repeat does not turn image metadata into plain text");
      press("u");
      assert(input.text === "draft" && view.composer.spans.length === 0, "undo removes the inserted image span");
      key("r", 4); assert(input.text === "IMGdraft" && view.composer.spans.length === 1 && "blob" in view.composer.spans[0], "redo restores image metadata");
      view.composer.spans = [];

      // Prepare rendered transcript rows without painting a frame or opening a terminal.
      const transcript = view.transcript;
      transcript.partsOf = () => [{ type: "text", id: 0, text: "foo,bar baz\nqux/quux end" }];
      transcript.setOutline([{ type: "user", id: 100 }], null);
      transcript._rebuild(80);
      view.focusRegion("transcript");
      press("gg0");
      const start = transcript.caret;
      assert(start !== null, "native transcript cursor seeds");
      press("W"); assert(transcript.caret?.col === 8, "transcript W skips punctuation");
      press("B"); assert(transcript.caret?.col === 0, "transcript B skips punctuation");
      press("vW");
      assert(transcript.selection !== null && transcript.caret?.col === 8, "transcript WORD motion keeps native visual selection");
      esc();
      press("W");
      assert(transcript.caret?.col === 0 && transcript.caret.row !== start?.row, "transcript W crosses a row");
      press("W"); assert(transcript.caret?.col === 9, "transcript W crosses a slash-separated WORD");
      press("B"); assert(transcript.caret?.col === 0, "transcript B moves to row start");
      press("B"); assert(transcript.caret?.col === 8 && transcript.caret.row === start?.row, "transcript B crosses to the previous WORD");
      reset("abc");
      let navigated = false;
      const commands = /** @type {typeof c.tui.command} */ (Object.getPrototypeOf(c.tui.command));
      const unbind = c.advise(commands, "perform", "around", (next, command, ...args) => {
        if (command === "focus:up") { navigated = true; return true; }
        return next(command, ...args);
      });
      press("d"); key("k", 4);
      assert(navigated && c.tui.keymap.pending === null, "control K navigates and cancels a pending operator");
      press("x"); assert(input.text === "bc", "navigation cancels grammar even when no pane changes focus");
      unbind();
      reset(""); press("/"); assert(input.text === "/" && mode.mode(view.composer) === "insert", "slash command shortcut stays intact");
      c.print("Extended Vim regression checks passed");
    });
  },
}));
