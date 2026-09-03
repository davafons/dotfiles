import { Chat, focusedChat } from "yuke:chat";
import { composerVim } from "yuke:composer-vim";
import { commands } from "yuke";
import { root } from "yuke:core";
import { plugins } from "yuke:ext";
import { notice } from "yuke:notice";
import { term } from "yuke:term";
import { transcriptVim } from "yuke:transcript-vim";

// Use Vim-style modal editing and pane navigation. In composer normal mode,
// Ctrl-W h/j/k/l moves between panes; Ctrl-W v/s splits and Ctrl-W c closes.
plugins.use(composerVim);
plugins.use(transcriptVim);

// Use direct Vim-style pane navigation from any focused pane.
plugins.use({
  name: "vim-pane-navigation",
  apply(ctx) {
    ctx.inject(["tui"], (ctx) => {
      ctx.tui.keymap({
        "ctrl+h": "focus:left",
        "ctrl+j": "focus:down",
        "ctrl+k": "focus:up",
        "ctrl+l": "focus:right",
      });
    });
  },
});

// Vim-like panel management through one discoverable slash command:
// /panel split, /panel vsplit, /panel close, and /panel only.
commands.define({
  name: "panel",
  title: "Panel",
  description: "split, close, or keep the current panel",
  args: true,
  run(arg = "") {
    const action = arg.trim().split(/\s+/, 1)[0] || "";
    if (action === "split" || action === "vsplit") {
      const chat = new Chat();
      if (!root.split(action === "split" ? "col" : "row", chat.view)) chat.dispose();
      return;
    }
    if (action === "close") {
      root.close();
      return;
    }
    if (action === "only") {
      const current = root.focused;
      if (current) root.setActive(current);
      return;
    }
    notice.show("usage: /panel split | vsplit | close | only");
  },
});

// Match the usual terminal-agent behavior: the built-in Ctrl-C binding cancels, and a second
// Ctrl-C on the same empty composer exits. Any other interaction starts a fresh sequence.
let armedComposer = null;

plugins.use({
  name: "ctrl-c-cancel-quit",
  apply(ctx) {
    ctx.inject(["tui"], (ctx) => {
      const disarm = () => { armedComposer = null; };

      ctx.on("key.press", (ev) => {
        if (ev.event === "press" && ev.code === "char" && ev.char === "c" && (ev.mods & 4) !== 0) return;
        disarm();
      });
      ctx.on("composer.changed", disarm);
      ctx.on("pane.focused", disarm);
      ctx.on("region.focused", disarm);
      ctx.tui.status({
        side: "left",
        order: -1,
        render: () => armedComposer ? "press Ctrl-C again to exit" : "",
      });
      ctx.on("key.press", (ev) => {
        if (!(ev.event === "press" && ev.code === "char" && ev.char === "c" && (ev.mods & 4) !== 0)) return;
        const chat = focusedChat();
        if (!chat) return;
        const composer = chat.composer;
        if (composer.text === "" && armedComposer === composer) {
          armedComposer = null;
          term.quit();
        } else {
          armedComposer = composer.text === "" ? composer : null;
        }
      });
    });
  },
});
