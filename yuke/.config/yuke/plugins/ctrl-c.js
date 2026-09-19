import { currentPane } from "yuke:session";
import { quit } from "yuke:ui";
/** @import { Plugin } from "yuke" */
/** @import { Composer } from "yuke:ui" */

/** Clear with Ctrl+C; a second press on the same empty normal composer requests quit. */
export const ctrlC = /** @type {Plugin} */ ({
  name: "ctrl-c",
  apply(ctx) {
    ctx.inject(["tui", "composer-vim"], (c) => {
      /** @type {Composer | null} */
      let armed = null;
      const disarm = () => { armed = null; };

      c.on("key.pressed", (ev) => {
        if (ev.event === "release") return;
        if (ev.code === "char" && ev.char === "c" && ev.mods === 4 &&
            !c.tui.root.overlays.some((layer) => layer.modal !== false)) return;
        disarm();
      });
      c.on("composer.changed", disarm);
      c.on("composer.attached", disarm);
      c.on("pane.focused", disarm);
      c.on("pane.closed", disarm);
      c.on("region.focused", disarm);
      c.on("session.current.changed", disarm);
      c.on("mouse.received", disarm);
      c.on("paste.received", disarm);
      c.on("focus.changed", disarm);

      c.tui.keymap.add({
        "ctrl+c": (ev) => {
          if (ev.type !== "key" || ev.event !== "press") return true;
          const pane = currentPane();
          const composer = pane?.composer;
          if (!composer || c.tui.root.active !== pane) return false;
          if (composer.text !== "") {
            composer.text = "";
            c["composer-vim"].setMode(composer, "normal");
            return true;
          }
          if (c["composer-vim"].mode(composer) === "insert") {
            disarm();
            c["composer-vim"].setMode(composer, "normal");
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

      c.tui.status.add({
        side: "left",
        order: -1,
        render: () => armed ? "press Ctrl+C again to exit" : "",
      });
    });
  },
});
