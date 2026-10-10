//! Pane navigation and slash commands, separate from the Vim grammar.
import { events } from "yuke";
import { ChatView } from "yuke:chat";
/** @import { ViewLike } from "yuke:ui" */
/** Register pane navigation when TUI and Vim exist. The context owns advice and keys; host failures throw. @param {import("yuke").Context} ctx */
export default function (ctx) {
  const tuiBorrow = ctx.get("tui"), vimBorrow = ctx.get("composer-vim");
  if (!tuiBorrow || !vimBorrow) return;
  const tui = tuiBorrow, vim = vimBorrow;
  const cancelEditing = () => { const pane = tui.root.active; if (pane instanceof ChatView) vim.cancel(pane.composer); };
  // Register through the owned facade. Apply dispatch advice to its shared registry.
  const sharedKeymap = /** @type {typeof tui.keymap} */ (Object.getPrototypeOf(tui.keymap));
  tui.keymap.add({
    "/": () => {
      const view = tui.root.active;
      if (!(view instanceof ChatView)) return false;
      view.focusRegion("composer");
      vim.setMode(view.composer, "insert");
      view.composer.input.insert("/");
      return true;
    },
  }, "chat && !overlay && (transcript || vim_mode == normal)");
  tui.keymap.add({
    "ctrl+h": "focus:left",
    "ctrl+j": "focus:down",
    "ctrl+k": "focus:up",
    "ctrl+l": "focus:right",
  }, "chat && !overlay");
  /** @type {Record<string, string>} */
  const navigation = { h: "focus:left", k: "focus:up", l: "focus:right" };
  /** @param {Parameters<typeof tui.keymap.onKey>[0]} ev */
  function navigate(ev) {
    if (ev.event === "release" || ev.mods !== 4 || ev.code !== "char" ||
        tui.root.active?.name !== "chat" ||
        tui.root.overlays.some((layer) => layer.modal !== false)) return false;
    if (events.bail("prompt-history:control-key", ev)) {
      cancelEditing(); sharedKeymap.pending = null;
      return true;
    }
    const command = navigation[ev.char];
    if (!command) return false;
    cancelEditing(); sharedKeymap.pending = null;
    return tui.command.perform(command);
  }
  // Ctrl+K is also a default chord prefix, so navigation must run before the chord wait.
  ctx.advise(sharedKeymap, "onKey", "around", (next, ev) => navigate(ev) || next(ev));
  // Insert mode reads Ctrl+H before the keymap, so pane navigation intercepts it.
  const bound = new WeakSet();
  /** @param {ViewLike} view */
  function bind(view) {
    if (view.name !== "chat" || typeof view.onKey !== "function" || bound.has(view)) return;
    bound.add(view);
    const keyed = /** @type {ViewLike & { onKey: NonNullable<ViewLike["onKey"]> }} */ (view);
    ctx.advise(keyed, "onKey", "around", (next, ev) => {
      if (ev.type === "key") {
        const chat = /** @type {ChatView} */ (view);
        if (ev.event !== "release" && ev.code === "char" && ev.char === "j" && ev.mods === 4 &&
            chat.focus === "composer" && vim.mode(chat.composer) === "insert") {
          chat.composer.input.insert("\n");
          return true;
        }
        if (navigate(ev)) return true;
      }
      return next(ev);
    });
  }
  ctx.on("pane.focused", bind);
  if (tui.root.active) bind(tui.root.active);

  tui.command.add("panel", {
    desc: "Split, close, or keep the current panel",
    slash: true,
    args: true,
    run(arg = "") {
      const action = String(arg).trim();
      if (action === "split") tui.command.perform("window:split-down");
      else if (action === "vsplit") tui.command.perform("window:split-right");
      else if (action === "close") tui.command.perform("window:close");
      else if (action === "only") {
        const root = tui.root;
        const active = root.active;
        if (!active) return;
        const leaves = root.root_node?.leaves() ?? [];
        for (const leaf of leaves) {
          if (leaf.shape.type === "leaf" && leaf.shape.view !== active) root.close(leaf.shape.view);
        }
      } else ctx.interaction.notify("usage: /panel split | vsplit | close | only");
    },
  });
}
