//! Observed request phases belong to display-only transcript blocks, not engine messages.
import { client } from "yuke";
import { Transcript } from "yuke:chat";
import { sessions } from "yuke:session";
import { clip } from "yuke:ui";

/** @typedef {{ key: string, label: string, start: number, end: number | null }} Phase */
/** @typedef {{ id: number, after: number | null, phases: Phase[], parts: Wire.AssistantPart[] }} Card */
/** @typedef {{ run: number, card: Card | null, current: Phase | null, cards: Map<number | null, Card[]> }} Timeline */

/** Register display-only phase blocks. The context owns observations and rows; missing UI skips them and host failures throw. @param {import("yuke").Context} ctx @param {number} periodMs @returns {import("./index.js").Feature | undefined} */
export default function(ctx, periodMs) {
  const tui = ctx.get("tui");
  const chat = ctx.get("chat");
  if (!tui || !chat) return;
  /** @type {Map<string, Timeline>} */
  const timelines = new Map();
  /** @type {Map<number, Card>} */
  const cards = new Map();
  /** @type {WeakSet<Transcript>} */
  const attached = new WeakSet();
  let nextId = -1;

  /** @param {Transcript} transcript */
  const sessionOf = (transcript) => {
    for (let i = 0; i < sessions.length; i++) {
      const session = sessions[i];
      for (let j = 0; j < session.views.length; j++) if (session.views[j].transcript === transcript) return session;
    }
    return null;
  };
  /** @param {Transcript} transcript */
  const attach = (transcript) => {
    if (attached.has(transcript)) return;
    attached.add(transcript);
    ctx.advise(transcript, "partsOf", "around", (next, id) => cards.get(id)?.parts ?? next(id));
    if (transcript.partOf) ctx.advise(/** @type {{ partOf: NonNullable<Transcript["partOf"]> }} */ (transcript), "partOf", "around", (next, id, part, cursor) => cards.has(id) ? null : next(id, part, cursor));
    if (transcript.partTextPage) ctx.advise(/** @type {{ partTextPage: NonNullable<Transcript["partTextPage"]> }} */ (transcript), "partTextPage", "around", (next, id, field, offset, limit) => cards.has(id) ? { text: "", next: null } : next(id, field, offset, limit));
  };
  ctx.advise(Transcript.prototype, "setOutline", "around", function(next, messages, active) {
    const session = sessionOf(this);
    const timeline = session?.sessionId ? timelines.get(session.sessionId) : null;
    if (!timeline || !timeline.cards.size || !messages.length) return next(messages, active);
    attach(this);
    /** @type {Parameters<Transcript["setOutline"]>[0]} */
    const shown = [];
    const first = timeline.cards.get(null);
    if (first) for (let i = 0; i < first.length; i++) shown.push({ id: first[i].id, type: "assistant" });
    for (let i = 0; i < messages.length; i++) {
      const message = messages[i];
      shown.push(message);
      const after = timeline.cards.get(message.id);
      if (after) for (let j = 0; j < after.length; j++) shown.push({ id: after[j].id, type: "assistant" });
    }
    return next(shown, active);
  });

  chat.render({
    part(part, env) {
      const card = cards.get(env.messageId);
      if (!card) return undefined;
      /** @type {import("yuke:chat").Rendered["rows"]} */
      const rows = [];
      const now = Date.now();
      for (let i = 0; i < card.phases.length; i++) {
        const phase = card.phases[i];
        const seconds = (Math.max(0, (phase.end ?? now) - phase.start) / 1000).toFixed(1);
        const text = (phase.end == null ? "→ " : "· ") + phase.label + " · " + seconds + "s";
        rows.push({ text: clip(text, Math.max(0, env.width - 2)), indent: 1, group: phase.end == null ? "TxToolHint" : "TxMeta" });
      }
      return { rows, source: "" };
    },
  });

  /** @param {string} id */
  const reload = (id) => {
    for (let i = 0; i < sessions.length; i++) if (sessions[i].sessionId === id) sessions[i].reload();
    tui.root.invalidate();
  };
  /** @param {string} id @param {Wire.SessionActivity | null} activity */
  const update = (id, activity) => {
    let timeline = timelines.get(id);
    const now = Date.now();
    if (!activity) {
      if (timeline) {
        timeline.cards.forEach(group => { for (let i = 0; i < group.length; i++) cards.delete(group[i].id); });
        timelines.delete(id);
        reload(id);
      }
      return;
    }
    const state = activity.state;
    if (state.type === "idle" || state.type === "running_tool") {
      if (timeline?.current && timeline.card) {
        timeline.current.end = now;
        chat.refresh(timeline.card.id, 0);
        timeline.current = null;
        timeline.card = null;
        tui.root.invalidate();
      }
      return;
    }
    const label = state.type === "waiting" ? "waiting for model" : state.type === "streaming" ? "receiving response" : state.type === "reasoning" ? "reasoning" : state.type === "building" ? "preparing request" : state.type === "retrying" ? "retry " + state.attempt : state.type === "compacting" ? "compacting" : "";
    if (!label) return;
    const key = state.type === "reasoning" ? state.type + ":" + state.message_id + ":" + state.part_id : state.type === "retrying" ? state.type + ":" + state.attempt : state.type;
    if (timeline?.run === state.run_id && timeline.current?.key === key) return;
    if (timeline?.current && timeline.card) {
      timeline.current.end = now;
      chat.refresh(timeline.card.id, 0);
    }
    if (!timeline) {
      timeline = { run: state.run_id, card: null, current: null, cards: new Map() };
      timelines.set(id, timeline);
    }
    if (timeline.run !== state.run_id) { timeline.run = state.run_id; timeline.card = null; }
    let inserted = false;
    if (!timeline.card) {
      const outline = client.sessionOutline(id);
      const after = outline?.messages.at(-1)?.id ?? null;
      /** @type {Card} */
      const card = { id: nextId--, after, phases: [], parts: [{ type: "tool", id: 0, call_id: "display-only", name: "phase_timing", arguments: "{}", state: { type: "completed", output: "", duration_ms: 0 } }] };
      timeline.card = card;
      let group = timeline.cards.get(after);
      if (!group) { group = []; timeline.cards.set(after, group); }
      group.push(card);
      cards.set(card.id, card);
      inserted = true;
    }
    timeline.current = { key, label, start: now, end: null };
    timeline.card.phases.push(timeline.current);
    if (inserted) reload(id);
    else { chat.refresh(timeline.card.id, 0); tui.root.invalidate(); }
  };
  for (let i = 0; i < sessions.length; i++) {
    const session = sessions[i];
    if (session.sessionId) update(session.sessionId, session.activity);
  }
  ctx.own(() => {
    timelines.clear();
    for (let i = 0; i < sessions.length; i++) sessions[i].reload();
    cards.clear();
    tui.root.invalidate();
  });
  return { periodMs, lastTick: 0, activity: update,
    live: () => { for (const timeline of timelines.values()) if (timeline.current) return true; return false; },
    tick: () => {
      for (const timeline of timelines.values()) if (timeline.current && timeline.card) chat.refresh(timeline.card.id, 0);
      tui.root.invalidatePaint();
    },
  };
}
