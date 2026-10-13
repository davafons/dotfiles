//! Personal ctrl-c registrations on manifest-owned capabilities.
import { currentPane } from "yuke:session";
import { quit } from "yuke:ui";
/** @import { Composer } from "yuke:ui" */

/** Clear with Ctrl+C; a second press on the same empty normal composer requests quit. */
/** Preserve the personal ctrl-c workflow with the one Vim service. No TUI or editor skips it; host failures throw. @param {import("yuke").Context} ctx */
export default function (ctx) {
  const tui = ctx.get("tui"), vim = ctx.get("composer-vim");
  if (!tui || !vim) return;
  /** @type {Composer | null} */
  let armed = null;
  const disarm = () => { armed = null; };

  ctx.on("key.pressed", (ev) => {
    if (ev.event === "release") return;
    if (ev.code === "char" && ev.char === "c" && ev.mods === 4 &&
        !tui.root.overlays.some((layer) => layer.modal !== false)) return;
    disarm();
  });
  ctx.on("composer.changed", disarm);
  ctx.on("composer.attached", disarm);
  ctx.on("pane.focused", disarm);
  ctx.on("pane.closed", disarm);
  ctx.on("region.focused", disarm);
  ctx.on("session.current.changed", disarm);
  ctx.on("mouse.received", disarm);
  ctx.on("paste.received", disarm);
  ctx.on("focus.changed", disarm);

  tui.keymap.add({
    "ctrl+c": (ev) => {
      if (ev.type !== "key" || ev.event !== "press") return true;
      const pane = currentPane();
      const composer = pane?.composer;
      if (!composer || tui.root.active !== pane) return false;
      if (composer.text !== "") {
        composer.text = "";
        vim.setMode(composer, "normal");
        return true;
      }
      if (vim.mode(composer) === "insert") {
        disarm();
        vim.setMode(composer, "normal");
        return true;
      }
      if (armed === composer) {
        disarm();
        quit();
        return true;
      }
      pane.session.interrupt();
      armed = composer;
      return true;
    },
  }, "chat && !overlay");

  tui.status.add({
    side: "left",
    order: -1,
    render: () => armed ? "press Ctrl+C again to exit" : "",
  });
}
