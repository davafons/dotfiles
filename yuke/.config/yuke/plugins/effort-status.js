//! Show the selected reasoning effort immediately after the model in the status bar.
import { client } from "yuke";
import { Session, currentEntry, currentPane, sessions } from "yuke:session";
/** @import { Plugin } from "yuke" */

/** The reasoning effort beside the built-in model status segment. */
export const effortStatus = /** @type {Plugin} */ ({
  name: "effort-status",
  apply(ctx) {
    ctx.inject(["tui"], (c) => {
      /** @type {WeakMap<Session, { selector: string, reasoning: string }>} */
      const pending = new WeakMap();
      /** @type {WeakMap<Session, string>} */
      const selected = new WeakMap();
      /** @type {WeakMap<Session, { id: string, reasoning: string }>} */
      const loaded = new WeakMap();
      /** @type {WeakMap<Session, string>} */
      const loading = new WeakMap();

      // Fetch the persisted choice when this plugin starts after the session was
      // selected. currentEntry() can be temporarily empty while a pane opens.
      const refresh = (session = currentPane()?.session) => {
        const id = session?.sessionId;
        if (!session || !id || loaded.get(session)?.id === id || loading.get(session) === id) return;
        loading.set(session, id);
        void client.sessionGet(id).then((entry) => {
          if (!ctx.alive || session.sessionId !== id) return;
          loaded.set(session, { id, reasoning: entry.session.reasoning });
          c.tui.root.invalidatePaint();
        }).catch(() => {
          // The pane or engine may disappear while the status refreshes.
        }).finally(() => {
          if (loading.get(session) === id) loading.delete(session);
        });
      };

      // model.changed omits the effort, so remember the setModel arguments and
      // publish them only after the engine accepts the choice and emits it.
      c.advise(Session.prototype, "setModel", "before", function (model, reasoning) {
        pending.set(this, { selector: model.selector, reasoning });
      });
      c.on("model.changed", (change) => {
        const session = change.sessionId === null
          ? currentPane()?.session
          : sessions.find((candidate) => candidate.sessionId === change.sessionId);
        if (!session || session.sessionId !== change.sessionId) return;
        const choice = pending.get(session);
        if (!choice || choice.selector !== change.model.selector) {
          selected.delete(session);
          loaded.delete(session);
          refresh(session);
          return;
        }
        pending.delete(session);
        selected.set(session, choice.reasoning);
      });
      c.on("session.current.changed", () => refresh());
      c.on("session.changed", () => refresh());
      c.on("index.changed", () => refresh());

      // The built-in model segment is order 10; this becomes its next neighbor.
      c.tui.status.add({
        side: "right",
        order: 11,
        render: () => {
          const session = currentPane()?.session;
          if (!session) return "";
          const chosen = selected.get(session);
          if (chosen !== undefined) return chosen;
          const entry = currentEntry();
          if (entry?.session.id === session.sessionId) return entry.session.reasoning;
          const persisted = loaded.get(session);
          if (persisted?.id === session.sessionId) return persisted.reasoning;
          refresh(session);
          return "";
        },
      });
      refresh();
    });
  },
});
