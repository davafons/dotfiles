//! Measure model phases that have no transcript part yet. Do not infer hidden reasoning.
import { client, events } from "yuke";
import { sessions } from "yuke:session";
import { toolHead } from "yuke:chat";
import { clip, measure } from "yuke:ui";

/** @typedef {{ key: string, label: string, anchor: string, start: number, end: number | null }} Phase */
/** @typedef {{ run: number, anchor: string, current: Phase | null, recent: Phase[] }} Timeline */

/** @param {Phase} phase @param {number} width */
function line(phase, width) {
  const seconds = (Math.max(0, (phase.end ?? Date.now()) - phase.start) / 1000).toFixed(1);
  const time = " · " + seconds + "s";
  const prefix = " " + (phase.end == null ? "→ " : "✓ ");
  const label = " → " + phase.label;
  const anchor = clip(phase.anchor, Math.max(0, width - measure(prefix + label + time)));
  return clip(prefix + anchor + label, Math.max(0, width - measure(time))) + time;
}
/** Register the migrated phase-timers operations. The plugin owns registrations; host failures throw. @param {import("yuke").Context} parent */
export default function(parent) {

    {
const tuiBorrow = parent.get("tui");
if (tuiBorrow) {
const c = { ctx: parent, tui: tuiBorrow };

      /** @type {Map<string, Timeline>} */
      const timelines = new Map();
      /** @param {string} id @param {Wire.SessionActivity | null} activity */
      const update = (id, activity) => {
        if (!activity) { timelines.delete(id); c.tui.root.invalidate(); return; }
        const state = activity.state;
        let timeline = timelines.get(id);
        if (state.type === "idle") {
          if (timeline?.current) { timeline.current.end = Date.now(); timeline.current = null; }
          c.tui.root.invalidate();
          return;
        }
        if (!timeline || timeline.run !== state.run_id) {
          timeline = { run: state.run_id, anchor: "request", current: null, recent: [] };
          timelines.set(id, timeline);
        }
        if (state.type === "running_tool") {
          const part = client.sessionPart(id, state.message_id, state.part_id)?.part;
          const head = part?.type === "tool" ? toolHead(part, {}) : null;
          timeline.anchor = head ? "after " + head.verb + (head.subject ? " " + head.subject : "") : "after " + state.tool_name;
        }
        const label = state.type === "waiting" ? "waiting for model" : state.type === "streaming" ? "responding" : state.type === "reasoning" ? "reasoning" : state.type === "building" ? "preparing request" : state.type === "retrying" ? "retry " + state.attempt : state.type === "compacting" ? "compacting" : "";
        const key = state.type === "reasoning" ? state.type + ":" + state.message_id + ":" + state.part_id : state.type === "retrying" ? state.type + ":" + state.attempt : state.type;
        if (timeline.current?.key === key) return;
        if (timeline.current) timeline.current.end = Date.now();
        timeline.current = label ? { key, label, anchor: timeline.anchor, start: Date.now(), end: null } : null;
        if (timeline.current) {
          timeline.recent.push(timeline.current);
          if (timeline.recent.length > 3) timeline.recent.shift();
        }
        c.tui.root.invalidate();
      };
      c.ctx.on("activity.changed", update);
      for (let i = 0; i < sessions.length; i++) {
        const session = sessions[i];
        if (session.sessionId) update(session.sessionId, session.activity);
      }

      // Keep the queue owner's rows. The public strip event is a bail event, so a
      // second strip listener alone would hide the queued messages.
      c.ctx.advise(events, "bail", "around", (next, name, ...args) => {
        const original = next(name, ...args);
        if (name !== "chat.strip") return original;
        const view = /** @type {import("yuke:chat").ChatView} */ (args[0]);
        const timeline = view.session.sessionId ? timelines.get(view.session.sessionId) : null;
        if (!timeline?.recent.length) return original;
        const rows = timeline.recent.map((phase) => ({ text: line(phase, view.rect.w), group: phase.end == null ? "TxToolHint" : "TxMeta" }));
        return /** @type {typeof original} */ ([...rows, ...(/** @type {{ text: string, group?: string }[]} */ (original) || [])]);
      });
      const pulse = { periodMs: 100 };
      c.tui.tickable({
        needsTick: () => {
          for (const timeline of timelines.values()) if (timeline.current) return pulse;
          return null;
        },
        tick: () => c.tui.root.invalidate(),
      });
      c.ctx.own(() => { timelines.clear(); });
}
}
  
}
