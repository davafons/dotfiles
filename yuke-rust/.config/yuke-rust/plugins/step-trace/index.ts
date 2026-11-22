import type { PluginContext } from "yuke:plugins";
import type { Infer } from "yuke:tools";

export const optionsSchema = { type: "object", properties: { enabled: { type: "boolean" } } } as const;

/** Log tool lifecycle metadata when enabled. Argument bodies and tool output never enter the trace. */
export function apply(ctx: PluginContext<Infer<typeof optionsSchema>>): (() => void) | undefined {
  if (ctx.options.enabled !== true) return;
  const calls = new Map<string, { readonly name: string; readonly start: number; updated: number }>();
  let timer: ReturnType<typeof setInterval> | undefined;
  let lastPulse = Date.now();
  let lastReport = lastPulse;
  const log = (event: string, fields: Record<string, unknown>): void =>
    console.log("STEP_TRACE", JSON.stringify({ time_ms: Date.now(), event, ...fields }));
  ctx.addListener("session.update", ({ sessionId, update }) => {
    if (update.kind !== "toolStarted" && update.kind !== "toolOutput" && update.kind !== "toolFinished") return;
    const key = `${sessionId}:${update.position.eventNumber}:${update.position.blockIndex}`;
    const now = Date.now();
    if (update.kind === "toolStarted") {
      calls.set(key, { name: update.call.name, start: now, updated: now });
      log("tool.started", { session: sessionId, site: key, name: update.call.name });
    } else if (update.kind === "toolOutput") {
      const call = calls.get(key);
      if (call !== undefined) call.updated = now;
    } else {
      log("tool.finished", {
        session: sessionId,
        site: key,
        duration_ms: update.durationMs,
        is_error: update.result.isError,
      });
      calls.delete(key);
    }
    if (calls.size === 0 && timer !== undefined) {
      clearInterval(timer);
      timer = undefined;
    } else if (timer === undefined) {
      lastPulse = lastReport = now;
      timer = setInterval(() => {
        const at = Date.now();
        const gap = at - lastPulse - 1000;
        if (gap > 2000 || gap < -1000) log("clock_or_event_loop_gap", { gap_ms: gap });
        lastPulse = at;
        if (at - lastReport < 30_000) return;
        lastReport = at;
        calls.forEach((call, site) => {
          log("tool.still_unsettled", {
            site,
            name: call.name,
            elapsed_ms: at - call.start,
            silence_ms: at - call.updated,
          });
        });
      }, 1000);
    }
  });
  return () => {
    if (timer !== undefined) clearInterval(timer);
    calls.clear();
  };
}
