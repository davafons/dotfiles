//! Manifest entry with context-owned registrations and explicit resource lifetimes.

/** Register the migrated context-dashboard operations. The plugin owns registrations; host failures throw. @param {import("yuke").Context} parent */
export default function(parent) {

    {
const tuiBorrow = parent.get("tui");
if (tuiBorrow) {
const c = { ctx: parent, tui: tuiBorrow };

      let opening = false;
      let shown = false;
      let released = Promise.resolve();
      c.ctx.advise(c.tui.command.map["context:show"], "run", "around", async (_next) => {
          if (shown || opening) return;
          opening = true;
          try {
            await released;
            const { openContext } = await import("./context-view.js");
            if (!c.ctx.alive) return;
            const owner = c.ctx.resources("context-dialog");
            try {
              openContext(c, owner, () => { shown = false; released = Promise.resolve(owner.dispose()); });
              shown = true;
            } catch (error) { await owner.dispose(); throw error; }
          } catch (error) {
            if (c.ctx.alive) c.ctx.interaction.notify("Cannot open context: " + String(error), "error");
          } finally { opening = false; }
      });
}
}
  
}
