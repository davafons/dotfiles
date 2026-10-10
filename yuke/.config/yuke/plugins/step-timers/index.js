//! Live elapsed time on each tool and thought, not only on the prompt's run counter.
import { client } from "yuke";
import { Transcript, wrapRows } from "yuke:chat";
import { sessions } from "yuke:session";
import { clip, measure } from "yuke:ui";

/** @import { Render, Rendered } from "yuke:chat" */
/** @typedef {{ message: number, part: number, session?: string, started: number, elapsed: number, live: boolean }} Clock */

/** @param {number} ms */
function seconds(ms) {
  return (Math.max(0, ms) / 1000).toFixed(1) + "s";
}

/** Register the migrated step-timers operations. The plugin owns registrations; host failures throw. @param {import("yuke").Context} parent */
export default function(parent) {

    {
const tuiBorrow = parent.get("tui");
const chatBorrow = parent.get("chat");
if (tuiBorrow && chatBorrow) {
const c = { ctx: parent, tui: tuiBorrow, chat: chatBorrow };

      /** @type {Map<string, Clock>} */
      const clocks = new Map();
      /** @type {Set<Clock>} */
      const active = new Set();
      // Message and part IDs are local to a session, not globally unique.
      /** @type {WeakMap<Transcript, string>} */
      const drafts = new WeakMap();
      let draftId = 0;
      /** @param {Transcript} transcript */
      const sessionOf = (transcript) => {
        for (const session of sessions) for (const view of session.views) {
          if (view.transcript === transcript && session.sessionId) return session.sessionId;
        }
        let id = drafts.get(transcript);
        if (!id) { id = "draft:" + (++draftId); drafts.set(transcript, id); }
        return id;
      };
      /** @param {number} message @param {number} part @param {string} [session] */
      const keyFor = (message, part, session = "") => session + ":" + message + ":" + part;
      /** @param {number} message @param {number} part @param {string | undefined} [session] */
      const clockFor = (message, part, session) => {
        const key = keyFor(message, part, session);
        let clock = clocks.get(key);
        if (!clock) {
          clock = { message, part, session, started: Date.now(), elapsed: 0, live: true };
          clocks.set(key, clock);
          active.add(clock);
        } else if (session) clock.session = session;
        return clock;
      };
      /** @param {Clock} clock */
      const stop = (clock) => {
        if (clock.live) clock.elapsed = Math.max(0, Date.now() - clock.started);
        clock.live = false;
        active.delete(clock);
      };
      /** @param {number} message @param {Wire.AssistantPart} part @param {boolean} live @param {string | undefined} [session] */
      const observe = (message, part, live, session) => {
        if (part.type !== "reasoning" && part.type !== "tool") return;
        const key = keyFor(message, part.id, session);
        const ms = part.type === "reasoning" ? part.duration_ms : "duration_ms" in part.state ? part.state.duration_ms : undefined;
        if (typeof ms === "number") {
          const clock = clocks.get(key);
          if (clock) active.delete(clock);
          clocks.delete(key);
          return;
        }
        if (part.type === "tool" && part.state.type !== "running" && part.state.type !== "pending") {
          const clock = clocks.get(key);
          if (clock) stop(clock);
          return;
        }
        const clock = clockFor(message, part.id, session ?? "");
        if (part.type === "tool" && part.state.type === "running") clock.started = part.state.started_at_ms;
        if (!live) stop(clock);
      };

      // Engine observation starts clocks even when a part is folded or off screen.
      c.ctx.on("engine.drained", (ev) => {
        if (ev.type !== "session") return;
        const message = ev.id ?? client.sessionOutline(ev.session)?.active?.id;
        if (message != null) {
          const parts = client.sessionParts(ev.session, message);
          for (let i = 0; i < parts.length; i++) {
            const part = parts[i];
            if (part.type === "tool" || part.type === "reasoning") {
              const live = part.type === "tool" || i === parts.length - 1;
              observe(message, part, live, ev.session);
            }
          }
        }
        // The drain ID can name the next message. Re-read older active calls so
        // a folded/off-screen tool does not keep timing after it has completed.
        for (const clock of active) if (clock.session === ev.session) {
          const part = client.sessionPart(ev.session, clock.message, clock.part)?.part;
          if (part?.type === "tool" || part?.type === "reasoning") {
            observe(clock.message, part, true, ev.session);
          }
        }
        if (ev.kind === "gone" || ev.facts.includes("run.done")) {
          for (const clock of active) if (clock.session === ev.session) {
            stop(clock);
            c.chat.refresh(clock.message, clock.part);
          }
        }
      });

      /** @type {Render} */
      const look = {
        showEmptyReasoning: true,
        part(part, env, transcript) {
          if (part.type !== "reasoning") return undefined;
          const session = sessionOf(transcript);
          observe(env.messageId, part, env.live, session);
          const clock = clocks.get(keyFor(env.messageId, part.id, session));
          const live = part.duration_ms == null && env.live && clock?.live;
          const ms = part.duration_ms ?? (clock ? live ? Date.now() - clock.started : clock.elapsed : undefined);
          const verb = live ? "thinking" : "thought";
          const suffix = " · " + (ms == null ? "time unavailable" : seconds(ms));
          const width = Math.max(1, env.width - 2);
          const title = part.title ? " " + clip(part.title, Math.max(0, width - verb.length - suffix.length - 1)) : "";
          /** @type {Rendered["rows"]} */
          const rows = [{ segments: [
            { text: verb, group: "TxToolTitle" },
            { text: title, group: "TxToolArg" },
            { text: suffix, group: "TxToolHint" },
          ], indent: 1, header: !!part.text, stop: true }];
          if (env.expanded && part.text) rows.push(...wrapRows(part.text, width, "TxThought", 1));
          return { rows, source: part.text };
        },
      };
      c.chat.render(look);

      const pulse = { periodMs: 100 };
      c.tui.tickable({
        needsTick: () => active.size ? pulse : null,
        tick: () => {
          for (const clock of active) c.chat.refresh(clock.message, clock.part);
        },
      });
      c.ctx.own(() => { active.clear(); clocks.clear(); });
}
}
  
}
