//! Independently selectable commands, interruption and pane navigation.
import { readSettings } from "../../lib/settings.js";
import clear from "./clear.js";
import exit from "./exit.js";
import interrupt from "./interrupt.js";
import navigation from "./navigation.js";

/** Register enabled controls. Missing TUI skips them; invalid settings throw before registration. The context owns every effect. @param {import("yuke").Context} ctx */
export default async function(ctx) {
  if (!ctx.get("tui")) return;
  const options = await readSettings(ctx, { clearAlias: true, exitAliases: true, interrupt: true, navigation: true, panelCommand: true });
  if (!ctx.alive) return;
  if (options.clearAlias) clear(ctx);
  if (options.exitAliases) exit(ctx);
  if (options.interrupt) interrupt(ctx);
  if (options.navigation || options.panelCommand) navigation(ctx, options);
}
