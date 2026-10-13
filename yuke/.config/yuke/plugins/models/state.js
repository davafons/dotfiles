//! One owner for accepted model and reasoning choices across pickers and status.
import { client } from "yuke";
import { Session, currentEntry, currentPane, sessions } from "yuke:session";

/** Observe accepted model choices. Draft choices stay local; persisted choices refresh after startup and session changes. The context owns advice and listeners. @param {import("yuke").Context} ctx @param {import("yuke:ui").Tui} tui */
export function modelState(ctx, tui) {
  /** @type {WeakMap<Session, { selector: string, reasoning: string }>} */
  const pending = new WeakMap();
  /** @type {WeakMap<Session, { id: string | null, selector: string, reasoning: string }>} */
  const accepted = new WeakMap();
  /** @type {WeakMap<Session, string>} */
  const loading = new WeakMap();
  const refresh = (session = currentPane()?.session) => {
    const id = session?.sessionId;
    if (!session || !id || accepted.get(session)?.id === id || loading.get(session) === id) return;
    loading.set(session, id);
    const previous = accepted.get(session);
    void client.sessionGet(id).then(entry => {
      if (!ctx.alive || session.sessionId !== id || accepted.get(session) !== previous) return;
      accepted.set(session, { id, selector: entry.session.model, reasoning: entry.session.reasoning });
      tui.root.invalidatePaint();
    }).catch(() => {}).finally(() => { if (loading.get(session) === id) loading.delete(session); });
  };
  ctx.advise(Session.prototype, "setModel", "before", function(model, reasoning) {
    pending.set(this, { selector: model.selector, reasoning });
  });
  ctx.on("model.changed", change => {
    const session = change.sessionId === null ? currentPane()?.session : sessions.find(row => row.sessionId === change.sessionId);
    if (!session || session.sessionId !== change.sessionId) return;
    const choice = pending.get(session);
    pending.delete(session);
    if (choice?.selector === change.model.selector) accepted.set(session, { ...choice, id: session.sessionId });
    else { accepted.delete(session); refresh(session); }
    tui.root.invalidatePaint();
  });
  ctx.on("session.current.changed", () => refresh());
  ctx.on("session.changed", () => refresh());
  ctx.on("index.changed", () => refresh());
  ctx.once("ui.started", () => refresh());
  refresh();
  /** @param {Session} session */
  function reasoning(session) {
    const choice = accepted.get(session);
    if (choice?.id === session.sessionId && choice.selector === session.modelSelector()) return choice.reasoning;
    const entry = currentEntry();
    return entry?.session.id === session.sessionId ? entry.session.reasoning : "";
  }
  return {
    reasoning,
    /** @param {Session} session */
    async effortOf(session) {
      return session.sessionId ? (await client.sessionGet(session.sessionId)).session.reasoning : reasoning(session);
    },
  };
}
