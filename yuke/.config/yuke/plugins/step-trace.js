//! Diagnostic timing at engine, hook, and cancellation boundaries. Never log tool contents.
import { client } from "yuke";
import { sessions } from "yuke:session";
/** @import { Plugin } from "yuke" */
/** @typedef {{ session: string, message: number, part: number, name: string, fingerprint: string, observed: number, started: number | null, state: string, updated: number }} Call */

/** Non-cryptographic correlation ID, not a copy of potentially sensitive arguments.
 * @param {string} value
 */
function fingerprint(value) {
  let hash = 2166136261;
  for (let i = 0; i < value.length; i++) hash = Math.imul(hash ^ value.charCodeAt(i), 16777619);
  return (hash >>> 0).toString(16).padStart(8, "0");
}

export const stepTrace = /** @type {Plugin} */ ({
  name: "step-trace",
  apply(ctx) {
    /** @type {Map<string, Call>} */
    const calls = new Map();
    /** @type {Set<Call>} */
    const active = new Set();
    /** @type {Map<string, string>} */
    const phases = new Map();
    /** @type {Map<string, { state: string, run: number, started: number }>} */
    const phaseClocks = new Map();
    /** @type {ReturnType<typeof setInterval> | null} */
    let timer = null;
    let lastPulse = 0;
    let lastReport = 0;
    /** @param {string} event @param {Record<string, unknown>} fields */
    const log = (event, fields) => ctx.print("STEP_TRACE " + JSON.stringify({ time_ms: Date.now(), event, ...fields }));
    /** @param {Call} call */
    const site = (call) => ({ session: call.session, message: call.message, part: call.part, name: call.name, fingerprint: call.fingerprint });
    const disarm = () => {
      if (timer != null) clearInterval(timer);
      timer = null;
    };
    /** Resolve old tool IDs too: a coalesced drain may point at the NEXT message.
     * @param {string} [session]
     */
    const reconcile = (session) => {
      for (const call of active) {
        if (session && call.session !== session) continue;
        const part = client.sessionPart(call.session, call.message, call.part)?.part;
        if (part?.type === "tool") observe(call.session, call.message, part, false);
      }
    };
    const arm = () => {
      if (timer != null) return;
      lastPulse = lastReport = Date.now();
      timer = setInterval(() => {
        reconcile();
        const now = Date.now();
        const delay = now - lastPulse - 1000;
        if (delay > 2000 || delay < -1000) log("clock_or_event_loop_gap", { gap_ms: delay });
        lastPulse = now;
        if (now - lastReport < 30000) return;
        lastReport = now;
        for (const [session, phase] of phaseClocks) log("phase.still_active", {
          session, state: phase.state, run: phase.run, elapsed_ms: now - phase.started,
        });
        for (const call of active) log("tool.still_unsettled", {
          ...site(call), state: call.state, observed_elapsed_ms: now - call.observed,
          execution_elapsed_ms: call.started == null ? null : now - call.started,
          silence_ms: now - call.updated,
        });
      }, 1000);
    };
    /** @param {string} session @param {number} message @param {Wire.ToolPart & { type: "tool" }} part @param {boolean} [touch] */
    const observe = (session, message, part, touch = true) => {
      const key = session + ":" + message + ":" + part.id;
      const now = Date.now();
      const state = part.state;
      let call = calls.get(key);
      if (!call) {
        call = { session, message, part: part.id, name: part.name, fingerprint: fingerprint(part.arguments), observed: now, started: null, state: "unobserved", updated: now };
        calls.set(key, call);
      }
      if (touch || state.type !== call.state) call.updated = now;
      call.fingerprint = fingerprint(part.arguments);
      if (state.type === call.state) return;
      call.state = state.type;
      if (state.type === "running") call.started = state.started_at_ms;
      const settled = state.type !== "running" && state.type !== "pending";
      log(settled ? "tool.settled" : "tool." + state.type, {
        ...site(call), state: state.type, engine_started_at_ms: call.started,
        engine_duration_ms: "duration_ms" in state ? state.duration_ms ?? null : null,
        observed_elapsed_ms: now - call.observed,
        execution_elapsed_ms: call.started == null ? null : now - call.started,
      });
      if (settled) {
        active.delete(call);
        if (!active.size && !phaseClocks.size) disarm();
      } else {
        active.add(call);
        arm();
      }
    };
    ctx.on("engine.drained", (ev) => {
      if (ev.type !== "session") return;
      const relevant = ev.facts.some((fact) => fact.startsWith("tool.") || fact === "message.part_added" || fact === "message.committed" || fact === "run.done");
      if (relevant) {
        const message = ev.id ?? client.sessionOutline(ev.session)?.active?.id;
        if (message != null) {
          const parts = ev.part == null ? client.sessionParts(ev.session, message) : [client.sessionPart(ev.session, message, ev.part)?.part];
          for (const part of parts) if (part?.type === "tool") observe(ev.session, message, part);
        }
      }
      if (relevant) reconcile(ev.session);
      if (ev.facts.includes("run.done") || ev.kind === "gone") {
        phaseClocks.delete(ev.session);
        log("run.finished", { session: ev.session, kind: ev.kind, facts: ev.facts });
        for (const [key, call] of calls) if (call.session === ev.session) {
          if (active.delete(call)) log("tool.unsettled_at_run_end", { ...site(call), state: call.state });
          calls.delete(key);
        }
        if (!active.size && !phaseClocks.size) disarm();
      }
    });
    ctx.hook("tool.before", (call) => {
      log("tool.before", { session: call.context.session_id, name: call.name, fingerprint: fingerprint(call.arguments) });
      return undefined;
    });
    ctx.hook("tool.after", (call) => {
      // This hook has no session or part ID. Do not invent a match for parallel calls.
      log("tool.after", { name: call.name, fingerprint: fingerprint(call.arguments), is_error: !!call.is_error });
      return undefined;
    });
    ctx.on("activity.changed", (session, activity) => {
      reconcile(session);
      const state = activity?.state;
      const run = state && "run_id" in state ? state.run_id : null;
      const phase = state?.type ?? "closed";
      const part = state && "part_id" in state ? state.part_id : null;
      const message = state && "message_id" in state ? state.message_id : null;
      const queued = activity?.queued ?? 0;
      if (run == null || phase === "running_tool") phaseClocks.delete(session);
      else {
        const before = phaseClocks.get(session);
        if (!before || before.run !== run || before.state !== phase) {
          phaseClocks.set(session, { state: phase, run, started: Date.now() });
        }
      }
      if (active.size || phaseClocks.size) arm(); else disarm();
      const key = [run, phase, message, part, queued].join(":");
      if (phases.get(session) === key) return;
      if (activity) phases.set(session, key); else phases.delete(session);
      log("phase", { session, state: phase, run, message, part, queued });
    });
    ctx.advise(client, "sessionCancelRun", "around", (next, session, clearQueue, report) => {
      const started = Date.now();
      log("cancel.requested", { session, clear_queue: !!clearQueue });
      return next(session, clearQueue, report).then((result) => {
        log("cancel.resolved", { session, elapsed_ms: Date.now() - started });
        return result;
      }, (error) => {
        log("cancel.rejected", { session, elapsed_ms: Date.now() - started });
        throw error;
      });
    });
    log("loaded", {});
    // A profile reload during a silent wait must capture the already-open call.
    ctx.inject(["tui"], () => {
      for (const session of sessions) {
        if (!session.sessionId) continue;
        const message = client.sessionOutline(session.sessionId)?.active?.id;
        if (message != null) for (const part of client.sessionParts(session.sessionId, message)) {
          if (part.type === "tool") observe(session.sessionId, message, part);
        }
        const state = session.activity?.state;
        if (state && state.type !== "idle" && state.type !== "running_tool") {
          phaseClocks.set(session.sessionId, { state: state.type, run: state.run_id, started: Date.now() });
          log("phase.snapshot", { session: session.sessionId, state: state.type, run: state.run_id });
          arm();
        }
      }
    });
    ctx.own(() => { disarm(); active.clear(); calls.clear(); phases.clear(); phaseClocks.clear(); });
  },
});
