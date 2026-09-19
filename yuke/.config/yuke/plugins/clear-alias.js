//! Add /clear as an alias for the built-in /new command.
/** @import { Plugin } from "yuke" */

/** Provide `/clear` while the built-in new-chat command is available. */
export const clearAlias = /** @type {Plugin} */ ({
  name: "clear-alias",
  apply(ctx) {
    ctx.inject(["tui"], (c) => {
      c.tui.command.add("clear", {
        desc: "leave the session and start empty",
        slash: true,
        when: () => c.tui.command.available("chat:new"),
        run: () => c.tui.command.perform("chat:new"),
      });
    });
  },
});
