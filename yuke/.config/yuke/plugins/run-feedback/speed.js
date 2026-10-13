//! Live output speed beside the model; provider usage replaces the estimate at commit.
import { client, utf8 } from "yuke";
import { currentPane } from "yuke:session";
/** @typedef {{ id: number, started: number, bytes: number, stopped?: number }} Round */
/** @typedef {{ live?: Round, last?: string, committed?: number }} Speed */

/** @param {number} tokens @param {number} ms @param {boolean} [estimated] */
function rate(tokens, ms, estimated = false) {
  if (!Number.isFinite(tokens) || tokens <= 0 || !Number.isFinite(ms) || ms <= 0) return "— tok/s";
  return (estimated ? "~" : "") + (tokens * 1000 / ms).toFixed(1) + " tok/s";
}

/** Register the token-speed view when TUI exists. The context owns registrations; a host failure throws. @param {import("yuke").Context} ctx @param {number} periodMs @returns {import("./index.js").Feature | undefined} */
export default function (ctx, periodMs) {
  const tui = ctx.get("tui");
  if (!tui) return;
  /** @type {Map<string, Speed>} */
  const speeds = new Map();

  /** @param {string} session @param {Speed} speed @param {number} id */
  const committed = (session, speed, id) => {
    if (speed.committed === id) return;
    speed.committed = id;
    const round = speed.live?.id === id ? speed.live : undefined;
    if (round) {
      round.stopped ??= Date.now();
      speed.live = undefined;
    }
    speed.last = "— tok/s";
    // Read only the just-committed message, not the entire conversation.
    void client.request("session.history", { session_id: session, before_message_id: id + 1, limit: 1 }).then((page) => {
      if (!ctx.alive || speeds.get(session) !== speed || speed.committed !== id) return;
      const message = page.messages.find((item) => item.id === id && item.type === "assistant");
      if (!message || message.type !== "assistant") return;
      // Output already includes reasoning tokens. Never add reasoning again.
      // Stored completion timestamps include tool time; only use that fallback
      // for tool-free messages when a coalesced drain hid the live round.
      const ms = round ? (round.stopped ?? Date.now()) - round.started : message.content.some((part) => part.type === "tool")
        ? 0 : (message.time.completed_at_ms ?? 0) - message.time.created_at_ms;
      speed.last = message.tokens ? rate(message.tokens.output, ms) : "— tok/s";
      tui.root.invalidatePaint();
    }).catch(() => {
      // A removed session or failed history read must not break the status bar.
    });
  };

  /** @param {Parameters<import("yuke").Events["engine.drained"]>[0]} ev */
  const drain = (ev) => {
    if (ev.type !== "session") return;
    if (ev.kind === "gone") {
      speeds.delete(ev.session);
      tui.root.invalidatePaint();
      return;
    }
    let speed = speeds.get(ev.session);
    if (!speed) { speed = {}; speeds.set(ev.session, speed); }
    const outline = client.sessionOutline(ev.session);
    if (ev.facts.includes("message.committed")) {
      const last = outline?.messages.findLast((message) => message.type === "assistant");
      if (last && last.id !== speed.committed) committed(ev.session, speed, last.id);
    }
    const id = outline?.active?.id;
    if (id != null) {
      if (speed.live?.id !== id) speed.live = { id, started: Date.now(), bytes: 0 };
      const round = speed.live;
      const parts = client.sessionParts(ev.session, id);
      // Text, visible reasoning, and tool arguments are all model output.
      // Opaque signatures and tool results are not. Four UTF-8 bytes per token
      // is only an estimate; hidden reasoning cannot be measured live.
      round.bytes = parts.reduce((bytes, part) => bytes + utf8.encode(
        part.type === "text" || part.type === "reasoning" ? part.text : part.type === "tool" ? part.arguments : ""
      ).length, 0);
      const tool = parts.find((part) => part.type === "tool" && part.state.type !== "pending");
      if (tool) round.stopped ??= Date.now();
    }
    if (ev.facts.includes("message.discarded") || ev.facts.includes("run.done")) {
      // Interrupted/discarded drafts have no trustworthy provider token count.
      speed.live = undefined;
    }
    tui.root.invalidatePaint();
  };

  /** @param {{ sessionId: string | null }} change */
  const modelChanged = (change) => {
    if (change.sessionId) speeds.delete(change.sessionId);
    tui.root.invalidatePaint();
  };
  tui.status.add({
    side: "right",
    order: 12, // Immediately after the model (10) and reasoning effort (11).
    render: () => {
      const session = currentPane()?.session.sessionId;
      const speed = session ? speeds.get(session) : undefined;
      const round = speed?.live;
      return round ? rate(round.bytes / 4, (round.stopped ?? Date.now()) - round.started, true) : speed?.last ?? "— tok/s";
    },
  });
  const live = () => {
    const session = currentPane()?.session.sessionId;
    const round = session ? speeds.get(session)?.live : undefined;
    return !!round && round.stopped == null;
  };
  ctx.own(() => speeds.clear());
  return { periodMs, lastTick: 0, drain, modelChanged, live, tick: () => tui.root.invalidatePaint() };
}
