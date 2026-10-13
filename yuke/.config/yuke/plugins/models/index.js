//! Model controls and effort display share one accepted-choice owner.
import { currentPane } from "yuke:session";
import { readSettings } from "../../lib/settings.js";
import { modelState } from "./state.js";
import picker from "./picker.js";

/** Register enabled model features. Missing TUI skips them; invalid settings throw before registration. The context owns every effect. @param {import("yuke").Context} ctx */
export default async function(ctx) {
  const tui = ctx.get("tui");
  if (!tui) return;
  const options = await readSettings(ctx, { picker: true, effortPicker: true, aliases: true, effortStatus: true, modelKey: "ctrl+x m", effortKey: "ctrl+x e" });
  if (!ctx.alive || !options.picker && !options.effortPicker && !options.aliases && !options.effortStatus) return;
  const state = modelState(ctx, tui);
  if (options.picker || options.effortPicker || options.aliases) picker(ctx, tui, options, state);
  if (options.effortStatus) tui.status.add({ side: "right", order: 11, render: () => {
    const session = currentPane()?.session;
    return session ? state.reasoning(session) : "";
  } });
}
