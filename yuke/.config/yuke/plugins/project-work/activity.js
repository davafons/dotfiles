//! Read live session observations only while the work dialog is open.
import { client } from "yuke";
import { herdrSessionStates } from "../herdr/index.js";

/** @typedef {{label: string, running: boolean}} Observation */

/** Read owned observations without changing tasks or sessions. Unavailable sessions and failed remote reads never imply idle or completion. Invalid host reads yield unavailable. @param {string[]} ids @param {import("yuke").CancellationSignal} signal @returns {Promise<Map<string, Observation>>} */
export async function readActivity(ids, signal) {
  let remote = new Map();
  try { remote = await herdrSessionStates(signal); } catch { }
  /** @type {Map<string, Observation>} */
  const observed = new Map();
  for (let i = 0; i < ids.length; i++) {
    if (signal.aborted) break;
    const id = ids[i];
    if (!id || observed.has(id)) continue;
    let native = null;
    try { native = client.sessionActivity(id); } catch { }
    if (native) {
      const state = native.state.type;
      observed.set(id, { label: state.replaceAll("_", " ") + " · here", running: state !== "idle" });
    } else {
      const state = remote.get(id) || "unavailable";
      observed.set(id, { label: state + (remote.has(id) ? " · Herdr" : ""), running: state === "working" });
    }
  }
  return observed;
}
