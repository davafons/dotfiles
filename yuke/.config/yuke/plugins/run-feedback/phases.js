//! One display-only clock follows each model response; intermediate completed observations stay there.
import { client } from "yuke";
import { Transcript } from "yuke:chat";
import { sessions } from "yuke:session";
import { clip, measure } from "yuke:ui";
import { elapsed } from "./time.js";

/** @typedef {{ key: string, label: string, start: number, end: number | null }} Phase */
/** @typedef {{ id: number, message: number | null, phases: Phase[], current: Phase | null, part: Wire.AssistantPart }} Card */
/** @typedef {{ run: number, card: Card | null, records: Map<number, Card> }} Timeline */

/** Register display-only clocks at the end of native response parts. The context owns observations and rows; missing UI skips them and host failures throw. @param {import("yuke").Context} ctx @param {number} periodMs @returns {import("./index.js").Feature | undefined} */
export default function(ctx, periodMs) {
  const tui = ctx.get("tui"), chat = ctx.get("chat");
  if (!tui || !chat) return;
  /** @type {Map<string, Timeline>} */
  const timelines = new Map();
  /** @type {Map<number, Card>} */
  const cards = new Map();
  /** @type {WeakSet<Transcript>} */
  const attached = new WeakSet();
  let nextId = -2;

  /** @param {Transcript} transcript */
  const viewOf = transcript => {
    for (let i = 0; i < sessions.length; i++) {
      const views = sessions[i].views;
      for (let j = 0; j < views.length; j++) if (views[j].transcript === transcript) return views[j];
    }
    return null;
  };
  /** @param {Transcript} transcript @param {import("yuke:session").Session["views"][number]} view */
  const attach = (transcript, view) => {
    if (attached.has(transcript)) return;
    attached.add(transcript);
    ctx.advise(transcript, "partsOf", "around", (next, id) => {
      const pending = cards.get(id);
      if (pending) return [pending.part];
      const parts = next(id);
      const sid = view.session.sessionId;
      const card = sid ? timelines.get(sid)?.records.get(id) : null;
      if (!card) return parts;
      const shown = parts.slice();
      shown.push(card.part);
      return shown;
    });
    if (transcript.partOf) ctx.advise(/** @type {{ partOf: NonNullable<Transcript["partOf"]> }} */ (transcript), "partOf", "around", (next, id, part, cursor) => {
      const card = cards.get(part);
      return card ? { part: card.part, cursor: null, tail: false } : next(id, part, cursor);
    });
    if (transcript.partTextPage) ctx.advise(/** @type {{ partTextPage: NonNullable<Transcript["partTextPage"]> }} */ (transcript), "partTextPage", "around", (next, id, part, field, offset, limit) => cards.has(id) || cards.has(part) ? { text: "", next: null } : next(id, part, field, offset, limit));
  };
  ctx.advise(Transcript.prototype, "setOutline", "around", function(next, messages, active) {
    const view = viewOf(this);
    if (!view) return next(messages, active);
    attach(this, view);
    const sid = view.session.sessionId;
    const card = sid ? timelines.get(sid)?.card : null;
    if (!active && card?.current && card.message == null && messages.length) return next([...messages, { id: card.id, type: "assistant" }], active);
    return next(messages, active);
  });
  chat.render({
    fold(part) { return cards.has(part.id) ? false : undefined; },
    part(part, env) {
      const card = cards.get(part.id);
      if (!card) return undefined;
      if (!card.current && !card.phases.length) return { rows: [], source: "" };
      const now = Date.now();
      const last = card.phases[card.phases.length - 1];
      const span = card.current ? now - card.current.start : (last?.end ?? now) - (card.phases[0]?.start ?? now);
      const suffix = " · " + elapsed(span);
      const width = Math.max(0, env.width - 2);
      /** @type {import("yuke:chat").Rendered["rows"]} */
      const rows = [{ segments: [
        { text: clip("◷ " + (card.current?.label ?? "waited for model response"), Math.max(0, width - measure(suffix))), group: "TxToolTitle" },
        { text: clip(suffix, width), group: "TxToolHint" },
      ], indent: 1, header: true, stop: true }];
      if (env.expanded) for (let i = 0; i < card.phases.length; i++) {
        const phase = card.phases[i];
        rows.push({ text: clip(phase.label + " · " + elapsed((phase.end ?? now) - phase.start), Math.max(0, env.width - 3)), indent: 2, group: "TxMeta" });
      }
      return { rows, source: "" };
    },
  });

  /** @param {string} id */
  const reload = id => {
    for (let i = 0; i < sessions.length; i++) if (sessions[i].sessionId === id) sessions[i].reload();
    tui.root.invalidate();
  };
  /** @param {Card} card @param {number} now */
  const finish = (card, now) => {
    const last = card.phases[card.phases.length - 1];
    if (last && last.end == null) last.end = now;
    card.current = null;
    if (card.message != null) chat.refresh(card.message, card.id);
  };
  /** @param {string} id @param {Wire.SessionActivity | null} activity */
  const update = (id, activity) => {
    let timeline = timelines.get(id);
    const now = Date.now();
    if (!activity) {
      if (timeline) {
        timeline.records.forEach(card => { cards.delete(card.id); });
        if (timeline.card) cards.delete(timeline.card.id);
        timelines.delete(id);
        reload(id);
      }
      return;
    }
    const state = activity.state;
    if (state.type === "idle") {
      if (timeline?.card) {
        const pending = timeline.card.message == null;
        timeline.card.phases.length = 0;
        finish(timeline.card, now);
        if (pending) cards.delete(timeline.card.id);
        timeline.card = null;
        if (pending) reload(id);
        else tui.root.invalidate();
      }
      return;
    }
    const message = state.type === "running_tool" || state.type === "reasoning" ? state.message_id : client.sessionOutline(id)?.active?.id ?? null;
    const key = state.type === "reasoning" || state.type === "running_tool" ? state.type + ":" + state.message_id + ":" + state.part_id : state.type === "retrying" ? state.type + ":" + state.attempt : state.type;
    if (timeline?.run === state.run_id && timeline.card?.current?.key === key) return;
    if (!timeline) { timeline = { run: state.run_id, card: null, records: new Map() }; timelines.set(id, timeline); }
    let card = timeline.card;
    let structure = false;
    if (timeline.run !== state.run_id || (card?.message != null && card.message !== message)) {
      if (card) finish(card, now);
      card = null;
      timeline.run = state.run_id;
    }
    if (!card) {
      const cardId = nextId--;
      card = { id: cardId, message: null, phases: [], current: null, part: { type: "tool", id: cardId, call_id: "display-only", name: "phase_timing", arguments: "{}", state: { type: "completed", output: "", duration_ms: 0 } } };
      timeline.card = card;
      cards.set(cardId, card);
      structure = true;
    }
    if (card.message == null && message != null) {
      card.message = message;
      timeline.records.set(message, card);
      structure = true;
    }
    const last = card.phases[card.phases.length - 1];
    if (last && last.end == null) last.end = now;
    const label = state.type === "waiting" ? "waiting for model response" : state.type === "streaming" ? "reading model response" : state.type === "reasoning" ? "reading reasoning" : state.type === "running_tool" ? "running " + state.tool_name : state.type === "building" ? "preparing request" : state.type === "retrying" ? "waiting to retry model, attempt " + state.attempt : "compacting context";
    const phase = { key, label, start: state.type === "running_tool" ? state.started_at_ms : now, end: null };
    card.current = phase;
    if (state.type !== "running_tool") card.phases.push(phase);
    if (structure) reload(id);
    else if (message != null) { chat.refresh(message, card.id); tui.root.invalidatePaint(); }
  };
  for (let i = 0; i < sessions.length; i++) if (sessions[i].sessionId) update(/** @type {string} */ (sessions[i].sessionId), sessions[i].activity);
  ctx.own(() => {
    timelines.clear();
    for (let i = 0; i < sessions.length; i++) {
      const session = sessions[i];
      for (let j = 0; j < session.views.length; j++) session.views[j].transcript.setOutline([], null);
      session.reload();
    }
    cards.clear();
    tui.root.invalidate();
  });
  return { periodMs, lastTick: 0, activity: update,
    live: () => { for (const timeline of timelines.values()) if (timeline.card?.current) return true; return false; },
    tick: () => {
      for (const timeline of timelines.values()) if (timeline.card?.current && timeline.card.message != null) chat.refresh(timeline.card.message, timeline.card.id);
      tui.root.invalidatePaint();
    },
  };
}
