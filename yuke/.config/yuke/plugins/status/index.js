//! Manifest entry with context-owned registrations and explicit resource lifetimes.

/** Register the migrated status operations. The plugin owns registrations; host failures throw. @param {import("yuke").Context} parent */
export default function(parent) {

    {
const tuiBorrow = parent.get("tui");
if (tuiBorrow) {
const c = { ctx: parent, tui: tuiBorrow };

      let opening = false;
      let shown = false;
      let released = Promise.resolve();
      c.tui.command.add("status:show", {
        desc: "show model, context, session usage, and provider account limits", slash: "status",
        run: async () => {
          if (opening || shown) return;
          opening = true;
          try {
            await released;
            const { openStatus } = await import("./status-view.js");
            if (!c.ctx.alive) return;
            const owner = c.ctx.resources("status-dialog");
            try {
              openStatus(c, owner, () => { shown = false; released = Promise.resolve(owner.dispose()); });
              shown = true;
            } catch (error) { await owner.dispose(); throw error; }
          } catch (error) {
            if (c.ctx.alive) c.ctx.interaction.notify("Cannot open status: " + String(error), "error");
          } finally { opening = false; }
        },
      });
}
}
  
}
