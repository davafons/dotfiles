//! Model controls and effort display share one accepted-choice owner.
import { client } from "yuke";
import { currentPane } from "yuke:session";
import { readSettings } from "../../lib/settings.js";
import { modelState } from "./state.js";
import picker from "./picker.js";

/** Register enabled model features. Missing TUI skips them; invalid settings throw before registration. The context owns every effect. @param {import("yuke").Context} ctx */
export default async function(ctx) {
  const tui = ctx.get("tui");
  if (!tui) return;
  const options = await readSettings(ctx, { picker: true, effortPicker: true, aliases: true, effortStatus: true, modelKey: "ctrl+x m", effortKey: "ctrl+x e", startupModel: "", startupEffort: "" });
  if (!!options.startupModel !== !!options.startupEffort) throw new TypeError("startupModel and startupEffort must be set together");
  if (!ctx.alive || !options.picker && !options.effortPicker && !options.aliases && !options.effortStatus && !options.startupModel) return;
  const state = modelState(ctx, tui);
  if (options.startupModel) {
    let chosen = false;
    ctx.on("model.changed", () => { chosen = true; });
    ctx.once("ui.started", () => {
      void client.catalogList(null).then(catalog => {
        if (!ctx.alive || chosen || catalog.type === "unchanged") return;
        const model = catalog.models.find(row => row.selector === options.startupModel);
        if (!model || !model.reasoning_levels.includes(options.startupEffort)) {
          ctx.interaction.notify("Startup model or reasoning effort is unavailable; keeping the existing default.", "warn");
          return;
        }
        state.setDefault(model, options.startupEffort);
      }).catch(error => { if (ctx.alive) ctx.interaction.notify("Startup model unavailable: " + String(error), "warn"); });
    });
  }
  if (options.picker || options.effortPicker || options.aliases) picker(ctx, tui, options, state);
  if (options.effortStatus) tui.status.add({ side: "right", order: 11, render: () => {
    const session = currentPane()?.session;
    return session ? state.reasoning(session) : "";
  } });
}
