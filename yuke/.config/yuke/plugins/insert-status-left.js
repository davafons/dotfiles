//! Keep the Vim mode and editing status on the left side of the status bar.
import { vimImproved } from "./vim-improved.js";
/** @import { Plugin } from "yuke" */

/** Own the profile Vim plugins and place their existing status entries on the left. */
export const insertStatusLeft = /** @type {Plugin} */ ({
  name: "insert-status-left",
  apply(ctx) {
    ctx.inject(["tui"], (c) => {
      const borrowEntries = c.tui.status._list;
      const borrowExisting = new Set(borrowEntries);
      c.use(vimImproved);
      // Startup is synchronous, so each new entry belongs to the Vim children of this block.
      for (let i = 0; i < borrowEntries.length; i++) {
        const entry = borrowEntries[i];
        if (!borrowExisting.has(entry)) entry.side = "left";
      }
    });
  },
});
