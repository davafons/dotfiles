//! Profile Vim editing, transcript navigation, and panel commands.
import { events } from "yuke";
import { composerVim, transcriptVim } from "yuke:plugins";
import { ChatView } from "yuke:chat";
import { installVimOperators } from "./vim-operators.js";
/** @import { Plugin } from "yuke" */
/** @import { ViewLike } from "yuke:ui" */

/** Vim editing and transcript motion, direct pane navigation, and /panel commands. */
export const vimImproved = /** @type {Plugin} */ ({
  name: "vim-improved",
  apply(ctx) {
    ctx.use(composerVim);
    ctx.use(transcriptVim);

    ctx.inject(["tui", "composer-vim"], (c) => {
      const cancelEditing = installVimOperators(c);
      // Register through the owned facade. Apply dispatch advice to its shared registry.
      const sharedKeymap = /** @type {typeof c.tui.keymap} */ (Object.getPrototypeOf(c.tui.keymap));
      c.tui.keymap.add({
        "/": () => {
          const view = c.tui.root.active;
          if (!(view instanceof ChatView)) return false;
          view.focusRegion("composer");
          c["composer-vim"].setMode(view.composer, "insert");
          view.composer.input.insert("/");
          return true;
        },
      }, "chat && !overlay && (transcript || composer_vim == normal)");
      c.tui.keymap.add({
        "ctrl+h": "focus:left",
        "ctrl+j": "focus:down",
        "ctrl+k": "focus:up",
        "ctrl+l": "focus:right",
      }, "chat && !overlay");
      /** @type {Record<string, string>} */
      const navigation = { h: "focus:left", k: "focus:up", l: "focus:right" };
      /** @param {Parameters<typeof c.tui.keymap.onKey>[0]} ev */
      function navigate(ev) {
        if (ev.event === "release" || ev.mods !== 4 || ev.code !== "char" ||
            c.tui.root.active?.name !== "chat" ||
            c.tui.root.overlays.some((layer) => layer.modal !== false)) return false;
        if (events.bail("prompt-history:control-key", ev)) {
          cancelEditing(); sharedKeymap.pending = null;
          return true;
        }
        const command = navigation[ev.char];
        if (!command) return false;
        cancelEditing(); sharedKeymap.pending = null;
        return c.tui.command.perform(command);
      }
      // Ctrl+K is also a default chord prefix, so navigation must run before the chord wait.
      c.advise(sharedKeymap, "onKey", "around", (next, ev) => navigate(ev) || next(ev));
      // Insert mode reads Ctrl+H before the keymap, so pane navigation intercepts it.
      const bound = new WeakSet();
      /** @param {ViewLike} view */
      function bind(view) {
        if (view.name !== "chat" || typeof view.onKey !== "function" || bound.has(view)) return;
        bound.add(view);
        const keyed = /** @type {ViewLike & { onKey: NonNullable<ViewLike["onKey"]> }} */ (view);
        c.advise(keyed, "onKey", "around", (next, ev) => {
          if (ev.type === "key") {
            const chat = /** @type {ChatView} */ (view);
            if (ev.event !== "release" && ev.code === "char" && ev.char === "j" && ev.mods === 4 &&
                chat.focus === "composer" && c["composer-vim"].mode(chat.composer) === "insert") {
              chat.composer.input.insert("\n");
              return true;
            }
            if (navigate(ev)) return true;
          }
          return next(ev);
        });
      }
      c.on("pane.focused", bind);
      if (c.tui.root.active) bind(c.tui.root.active);

      c.tui.command.add("panel", {
        desc: "Split, close, or keep the current panel",
        slash: true,
        args: true,
        run(arg = "") {
          const action = String(arg).trim();
          if (action === "split") c.tui.command.perform("window:split-down");
          else if (action === "vsplit") c.tui.command.perform("window:split-right");
          else if (action === "close") c.tui.command.perform("window:close");
          else if (action === "only") {
            const root = c.tui.root;
            const active = root.active;
            if (!active) return;
            const leaves = root.root_node?.leaves() ?? [];
            for (const leaf of leaves) {
              if (leaf.shape.type === "leaf" && leaf.shape.view !== active) root.close(leaf.shape.view);
            }
          } else c.interaction.notify("usage: /panel split | vsplit | close | only");
        },
      });
    });
  },
});
