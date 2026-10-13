//! Selected feedback shares one engine observer and one idle-aware frame clock.
import { readSettings } from "../../lib/settings.js";
import speed from "./speed.js";
import phases from "./phases.js";
import steps from "./steps.js";

/** @typedef {{ periodMs: number, lastTick: number, live: () => boolean, tick: () => void, drain?: (ev: Parameters<import("yuke").Events["engine.drained"]>[0]) => void, activity?: (id: string, activity: Wire.SessionActivity | null) => void, modelChanged?: (change: { sessionId: string | null }) => void }} Feature */

/** Register selected feedback with one context-owned observer and ticker. Missing TUI skips it; invalid settings throw before registration. @param {import("yuke").Context} ctx */
export default async function(ctx) {
  const tui = ctx.get("tui");
  if (!tui) return;
  const options = await readSettings(ctx, { tokenSpeed: true, phaseTimers: true, stepTimers: true, speedRefreshMs: 250, timerRefreshMs: 100 });
  if (!ctx.alive) return;
  /** @type {Feature[]} */
  const features = [];
  if (options.tokenSpeed) { const feature = speed(ctx, options.speedRefreshMs); if (feature) features.push(feature); }
  if (options.phaseTimers) { const feature = phases(ctx, options.timerRefreshMs); if (feature) features.push(feature); }
  if (options.stepTimers) { const feature = steps(ctx, options.timerRefreshMs); if (feature) features.push(feature); }
  if (!features.length) return;
  if (features.some(feature => feature.drain)) ctx.on("engine.drained", ev => {
    for (let i = 0; i < features.length; i++) features[i].drain?.(ev);
  });
  if (features.some(feature => feature.activity)) ctx.on("activity.changed", (id, activity) => {
    for (let i = 0; i < features.length; i++) features[i].activity?.(id, activity);
  });
  if (features.some(feature => feature.modelChanged)) ctx.on("model.changed", change => {
    for (let i = 0; i < features.length; i++) features[i].modelChanged?.(change);
  });
  const pulse = { periodMs: 100 };
  tui.tickable({
    needsTick() {
      let period = Infinity;
      for (let i = 0; i < features.length; i++) if (features[i].live()) period = Math.min(period, features[i].periodMs);
      if (period === Infinity) return null;
      pulse.periodMs = period;
      return pulse;
    },
    tick() {
      const now = Date.now();
      for (let i = 0; i < features.length; i++) {
        const feature = features[i];
        if (feature.live() && now - feature.lastTick >= feature.periodMs) { feature.lastTick = now; feature.tick(); }
      }
    },
  });
}
