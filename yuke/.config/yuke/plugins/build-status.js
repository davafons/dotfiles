//! Show the version embedded in this running Yuke, not another binary on PATH.
import { client } from "yuke";
/** @import { Plugin } from "yuke" */

/** A cached build label from the running engine. It stays unchanged when the binary on disk is replaced. */
export const buildStatus = /** @type {Plugin} */ ({
  name: "build-status",
  apply(ctx) {
    ctx.inject(["tui"], (c) => {
      let label = "";
      c.tui.status.add({ side: "right", order: 100, render: () => label });
      void client.request("initialize").then((result) => {
        if (!c.alive) return;
        label = "yuke " + result.engine.version;
        c.tui.root.invalidatePaint();
      }).catch((error) => {
        if (!c.alive) return;
        label = "yuke build unknown";
        c.print("Cannot read the running Yuke build", error);
        c.tui.root.invalidatePaint();
      });
    });
  },
});
