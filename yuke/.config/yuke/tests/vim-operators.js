//! Headless profile regression checks. Import this file only from an isolated yuke check profile.
import { plugins, events } from "yuke";
import { ChatView } from "yuke:chat";
import { vimImproved } from "../plugins/vim-improved.js";
/** @import { Plugin } from "yuke" */
plugins.use(vimImproved);
plugins.use(/** @type {Plugin} */ ({
  name: "vim-operator-checks",
  apply(ctx) {
    ctx.inject(["tui", "composer-vim"], (c) => {
      const active = c.tui.root.active;
      if (!(active instanceof ChatView)) throw Error("missing chat pane");
      const view = active;
      const input = view.composer.input;
      const mode = c["composer-vim"];
      /** @param {boolean} ok @param {string} message */
      function assert(ok, message) { if (!ok) throw Error(message); }
      /** @param {string} chars */
      function press(chars) {
        for (const char of chars) c.tui.root.onEvent({ type: "key", code: "char", char, text: char, shifted: "", baseLayout: "", event: "press", mods: 0 });
      }
      /** @param {string} text @param {number} [caret] */
      function reset(text, caret = 0) {
        view.focusRegion("composer");
        mode.setMode(view.composer, "insert");
        input.setText(text);
        input.caret = caret;
        mode.setMode(view.composer, "normal");
      }
      /** @param {string} text @param {number} caret @param {string} keys @param {string} expected @param {number} [at] */
      function check(text, caret, keys, expected, at) {
        reset(text, caret);
        press(keys);
        assert(input.text === expected, keys + " text: " + JSON.stringify(input.text));
        if (at !== undefined) assert(input.caret === at, keys + " caret: " + input.caret);
      }
      check("alpha bravo\ncharlie", 0, "dw", "bravo\ncharlie", 0);
      press("P");
      assert(input.text === "alpha bravo\ncharlie", "dw register restores full word");
      check("alpha, bravo", 0, "dw", ", bravo");
      check("alpha bravo", 3, "dw", "alpbravo");
      check("alpha\nbravo", 4, "dw", "alph\nbravo");
      reset("alpha\n\nbravo", 6);
      press("dw");
      assert(input.text === "alpha\n\nbravo", "dw keeps an empty line");
      check("alpha bravo", 6, "db", "bravo", 0);
      check("alpha bravo", 0, "de", " bravo", 0);
      check("a bravo", 0, "de", "", 0);
      check("alpha bravo", 4, "de", "alph", 3);
      check("foo,bar baz", 0, "dW", "baz");
      check("foo,bar baz", 8, "dB", "baz");
      check("foo,bar baz", 0, "W", "foo,bar baz", 8);
      press("B");
      assert(input.caret === 0, "B treats punctuation as WORD content");
      check("alpha bravo", 0, "cw", " bravo", 0);
      assert(mode.mode(view.composer) === "insert", "cw enters insert mode");
      check("foo,bar baz", 0, "cW", " baz");
      check("alpha bravo", 2, "diw", " bravo", 0);
      check("alpha bravo", 6, "daw", "alpha", 4);
      check("alpha,bravo", 5, "diw", "alphabravo", 5);
      check("alpha  bravo", 5, "daw", "alpha", 4);
      check("alpha  ", 5, "daw", "", 0);
      check("alpha bravo", 0, "yaw", "alpha bravo", 0);
      press("$p");
      assert(input.text === "alpha bravoalpha ", "yaw includes trailing spaces");
      check("alpha bravo", 0, "ciw", " bravo");
      assert(mode.mode(view.composer) === "insert", "ciw enters insert mode");
      check("alpha bravo", 2, "yiw", "alpha bravo", 2);
      press("$p");
      assert(input.text === "alpha bravoalpha", "yiw register puts full word");
      check("a\nb\nc", 2, "dd", "a\nc", 2);
      press("P");
      assert(input.text === "a\nb\nc", "dd linewise put restores middle line");
      check("a\nb", 2, "dd", "a", 0);
      press("p");
      assert(input.text === "a\nb", "dd linewise put restores final line");
      check("a\nb\nc", 2, "cc", "a\n\nc", 2);
      assert(mode.mode(view.composer) === "insert", "cc enters insert mode");
      check("a\nb\nc", 2, "dj", "a", 0);
      check("a\nb\nc", 2, "dk", "c", 0);
      check("a\nb\nc", 2, "dG", "a", 0);
      check("a\nb\nc", 2, "dgg", "c", 0);
      check("a\nb\nc", 2, "yy", "a\nb\nc", 2);
      press("p");
      assert(input.text === "a\nb\nb\nc", "yy puts a line below");
      check("alpha bravo", 0, "dwD", "");
      press("P");
      assert(input.text === "bravo", "native-style D replaces operator register");
      check("alpha bravo", 0, "dwx", "ravo");
      press("P");
      assert(input.text === "bravo", "x replaces operator register");
      check("a👩‍💻b", 1, "x", "ab", 1);
      press("P");
      assert(input.text === "a👩‍💻b", "put preserves grapheme clusters");
      check("café, bravo", 0, "dw", ", bravo");
      check("e\u0301clair bravo", 0, "dw", "bravo");
      check("alpha bravo", 0, "d", "alpha bravo");
      assert(c.tui.keymap.pending?.kind === "operator", "operator has no timeout");
      c.tui.keymap.tick();
      assert(c.tui.keymap.pending?.stroke === "d", "tick keeps operator pending");
      press("iw");
      assert(input.text === " bravo", "three-stroke object dispatch");
      reset("alpha bravo");
      press("di");
      c.tui.root.onEvent({ type: "key", code: "esc", char: "", text: "", shifted: "", baseLayout: "", event: "press", mods: 0 });
      assert(c.tui.keymap.pending === null && input.text === "alpha bravo", "escape cancels a text object");
      press("d");
      view.focusRegion("transcript");
      assert(c.tui.keymap.pending === null, "focus change cancels operator");
      // Simulate the native yank result event. Do not access the desktop clipboard.
      press("yy");
      events.emit("clipboard.copied", { what: "selection", text: "from transcript", bytes: 15 });
      reset("draft");
      press("p");
      assert(input.text === "draft\nfrom transcript", "transcript line yank shares the put register");
      view.focusRegion("transcript");
      press("Y");
      events.emit("clipboard.copied", { what: "selection", text: "whole line", bytes: 10 });
      reset("draft");
      press("P");
      assert(input.text === "whole line\ndraft", "transcript Y preserves linewise put");
      // An unrelated clipboard event must not replace a composer register.
      check("alpha bravo", 0, "dw", "bravo");
      events.emit("clipboard.copied", { what: "selection", text: "unrelated", bytes: 9 });
      press("P");
      assert(input.text === "alpha bravo", "unrelated copy preserves operator register");
      reset("");
      press("/");
      assert(input.text === "/" && mode.mode(view.composer) === "insert", "slash still enters insert mode");
      c.print("Vim operator regression checks passed");
    });
  },
}));
