//! Optional inspection commands keep quota, context and historical readers separate.
import { readSettings } from "../../lib/settings.js";

/** Register selected insight views. Missing TUI skips them; invalid settings throw before registration. Views own their I/O until close. @param {import("yuke").Context} ctx */
export default async function(ctx) {
  const tui = ctx.get("tui");
  if (!tui) return;
  const options = await readSettings(ctx, { status: true, context: true, usage: true });
  if (!ctx.alive) return;
  const c = { ctx, tui };
  /** @param {string} name @param {() => Promise<(surface: typeof c, owner: ReturnType<import("yuke").Context["resources"]>, close: () => void) => void>} load */
  function dialog(name, load) {
    /** @type {"closed" | "opening" | "open"} */
    let state = "closed";
    let released = Promise.resolve();
    return async () => {
      if (state !== "closed") return;
      state = "opening";
      try {
        await released;
        const open = await load();
        if (!ctx.alive) return;
        const owner = ctx.resources(name);
        try {
          open(c, owner, () => { state = "closed"; released = Promise.resolve(owner.dispose()); });
          state = "open";
        } catch (error) { await owner.dispose(); throw error; }
      } catch (error) {
        if (ctx.alive) ctx.interaction.notify("Cannot open " + name + ": " + String(error), "error");
      } finally { if (state === "opening") state = "closed"; }
    };
  }
  if (options.status) tui.command.add("status", {
    desc: "show model, context, session usage, and provider account limits", slash: true,
    run: dialog("status", async () => (await import("./status-view.js")).openStatus),
  });
  if (options.context) {
    const show = dialog("context", async () => (await import("./context-view.js")).openContext);
    ctx.advise(tui.command.map["context:show"], "run", "around", () => show());
  }
  if (options.usage) (await import("./usage.js")).default(ctx);
}
