import { ui } from "yuke:ui";
/** @import { Plugin } from "yuke" */

/** Reverse model names within each provider in the model picker. Other pickers stay unchanged. */
export const modelsNewestFirst = /** @type {Plugin} */ ({
  name: "models-newest-first",
  apply(ctx) {
    ctx.inject(["tui"], (c) => {
      c.advise(ui, "pick", "filterArgs", ([opts]) => {
        if (opts?.title !== "select a model" || !opts.items?.length) return;
        // Only the model picker supplies these catalog fields.
        if (!opts.items.every((item) => item !== null && typeof item === "object" &&
            "provider" in item && typeof item.provider === "string" &&
            "name" in item && typeof item.name === "string")) return;
        const models = /** @type {{ provider: string, name: string }[]} */ (opts.items);
        // Keep provider order and reverse the built-in code-unit name order.
        const items = models.slice().sort((a, b) =>
          (a.provider < b.provider ? -1 : a.provider > b.provider ? 1 : 0) ||
          (a.name > b.name ? -1 : a.name < b.name ? 1 : 0));
        return [{ ...opts, items }];
      });
    });
  },
});
