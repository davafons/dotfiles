//! Pin metadata, register, search, and focus invariants that a text-only Vim comparison cannot check.
import { plugins, events } from "yuke";
import { ChatView } from "yuke:chat";
/** @import { Plugin } from "yuke" */
plugins.use(/** @type {Plugin} */ ({
  name: "vim-parity-invariants",
  apply(ctx) {
    ctx.inject(["tui", "composer-vim"], c => {
      const active = c.tui.root.active;
      if (!(active instanceof ChatView)) throw Error("missing chat");
      const view = active;
      const composer = view.composer, input = composer.input, mode = c["composer-vim"];
      composer.layout({ x: 0, y: 0, w: 80, h: 20 });
      /** @param {boolean} ok @param {string} message */
      function assert(ok, message) { if (!ok) throw Error(message); }
      /** @param {string} char @param {number} [mods] @param {Parameters<typeof c.tui.keymap.onKey>[0]["code"]} [code] */
      function key(char, mods = 0, code = "char") {
        c.tui.root.onEvent({ type: "key", code, char, text: mods ? "" : char, event: "press", mods, shifted: "", baseLayout: "" });
      }
      /** @param {string} chars */
      function press(chars) { for (const char of chars) key(char); }
      function esc() { key("", 0, "esc"); }
      /** @param {string} value @param {number} [at] */
      function reset(value, at = 0) {
        view.focusRegion("composer"); mode.setMode(composer, "insert"); input.setText(value);
        input.caret = at; mode.setMode(composer, "normal");
      }
      reset("a👩‍💻b", 1); press("r"); key("e\u0301");
      assert(input.text === "ae\u0301b" && input.caret === 1, "r replaces one complete grapheme");
      press("u"); assert(input.text === "a👩‍💻b", "replacement undo restores the original grapheme");
      reset("a👩‍💻b", 1); press("RX"); key("", 0, "backspace"); esc();
      assert(input.text === "a👩‍💻b", "replace backspace restores one complete grapheme");
      reset("abc"); composer.spans = [{ start: 0, end: 3 }]; press("RX"); key("", 0, "backspace"); esc();
      assert(input.text === "abc" && composer.spans.length === 1 && composer.spans[0].end === 3, "replace backspace restores collapsed metadata");
      composer.spans = [];
      reset("abc def"); press("RX"); esc(); press("iY"); esc();
      assert(input.text === "YXbc def", "leaving R removes the overwrite advice");
      reset("abc def ghi"); press("yiwwviwP"); press("w.");
      assert(input.text === "abc abc abc", "visual P keeps the source register for repeat");
      press("u"); assert(input.text === "abc abc ghi", "visual paste repeat is one undo group");
      reset("abc\ndef"); press('"zyy');
      reset("xyz"); press('V"zp');
      assert(input.text === "abc", "a linewise named register survives a replacement draft");
      reset("abc"); press('"zyiw'); reset("def"); press('"_diwp');
      assert(input.text === "abc", "black-hole delete does not replace the source register");
      reset("abc def"); press("i"); key("r", 4);
      assert(c.tui.keymap.pending?.stroke === "ctrl+r", "insert register owns the next stroke");
      esc(); assert(input.text === "abc def" && c.tui.keymap.pending === null, "escape cancels insert register without text changes");
      reset("abc\ndef"); press("maG"); press("'a");
      assert(input.caret === 0, "local line mark jump");
      press("dd"); press("uG'a"); assert(input.text === "abc\ndef" && input.caret === 0, "undo restores a deleted local mark");
      reset("replacement"); press("$'a"); assert(input.caret === 10, "replacement drafts clear local marks");
      reset("abc"); press("d"); press("gJ"); assert(input.text === "abc", "invalid operator join does not edit");
      reset("one two"); press("*"); reset("abc"); press("n");
      assert(input.caret === 0 && input.text === "abc", "a missing search result leaves the draft intact");
      reset("buffer"); press("yiw"); view.focusRegion("transcript"); press('"Y');
      events.emit("clipboard.copied", { what: "selection", text: "unrelated", bytes: 9 });
      reset("draft"); press("P");
      assert(input.text === "bufferdraft", "a register-name Y does not arm native yank capture");
      // Capture a native transcript yank event without invoking a native copy command.
      view.focusRegion("transcript"); press('"z');
      events.emit("key.pressed", { type: "key", code: "char", char: "Y", text: "Y", event: "press", mods: 0, shifted: "", baseLayout: "" });
      events.emit("clipboard.copied", { what: "selection", text: "saved transcript", bytes: 16 });
      reset("draft"); press('"zP');
      assert(input.text === "saved transcript\ndraft", "named registers accept native transcript yank events");

      c.print("Vim parity invariants passed");
    });
  },
}));
