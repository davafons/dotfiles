//! Resolve chat identity, live observations and native ownership outside drawing.
import { client, children } from "yuke";

/** @typedef {{label: string, running: boolean, ownerLabel?: string, title?: string, model?: string, parent?: string, presence?: "open" | "closed" | "unknown"}} Observation */
/** @typedef {{number: string, title: string, pane: string, workspace: string, state: string}} PaneInfo */
/** @typedef {{states: Record<string, "open" | "closed" | "unknown">, panes: Record<string, PaneInfo>, released: string[]}} Presence */
/** @typedef {(roots: Record<string, string>, openSessions: string[]) => Promise<Presence>} PresenceRead */

/** Read chat metadata and native tree presence. Only the probe can release confirmed closed owners. Missing metadata or failed probes remain unknown. No transcript is read. @param {string[]} ids @param {import("yuke").CancellationSignal} signal @param {PresenceRead} probe @returns {Promise<Map<string, Observation>>} */
export async function readActivity(ids, signal, probe) {
  if (signal.aborted) return new Map();
  /** @type {Map<string, Wire.SessionListItem | null>} */
  const items = new Map();
  /** @param {string} id */
  async function item(id) {
    if (items.has(id)) return items.get(id) || null;
    let value = null;
    try { value = await client.sessionGet(id); } catch { }
    if (signal.aborted) throw new Error("Work presence read canceled.");
    items.set(id, value);
    return value;
  }
  /** @type {Record<string, string>} */
  const roots = {};
  const unique = Array.from(new Set(ids.filter(Boolean)));
  for (let index = 0; index < unique.length; index++) {
    const id = unique[index];
    let current = await item(id);
    const seen = new Set();
    while (current && current.session.origin.type === "child" && seen.size < 32) {
      if (seen.has(current.session.id)) { current = null; break; }
      seen.add(current.session.id);
      current = await item(current.session.origin.site.session_id);
    }
    if (current && current.session.origin.type !== "child" && /^[0-9a-f]{32}$/u.test(current.session.id)) roots[id] = current.session.id;
  }
  /** @type {Map<string, Wire.SessionActivity | null>} */
  const nativeStates = new Map();
  const openSessions = [];
  const nativeIds = Array.from(new Set([...unique, ...Object.values(roots)]));
  for (let index = 0; index < nativeIds.length; index++) {
    const id = nativeIds[index];
    let native = null;
    try { native = client.sessionActivity(id); } catch { }
    nativeStates.set(id, native);
    if (native) openSessions.push(id);
  }
  /** @type {Presence} */
  let snapshot = { states: {}, panes: {}, released: [] };
  if (!signal.aborted) {
    try { snapshot = await probe(roots, openSessions); } catch { }
  }
  /** @type {Map<string, Observation>} */
  const observed = new Map();
  for (let index = 0; index < unique.length; index++) {
    if (signal.aborted) break;
    const id = unique[index];
    const current = items.get(id);
    const root = roots[id] || "";
    const directPane = snapshot.panes[id];
    const pane = directPane || snapshot.panes[root];
    const child = current?.session.origin.type === "child";
    const number = pane?.number && /^\d{1,6}$/u.test(pane.number) ? pane.number : "";
    const ownerLabel = (number ? "Agent " + number : child ? "Child agent" : "Chat") + (child ? " / " + children.id(current?.session.name || "child", id) : "");
    const nativeTitle = current?.session.title.trim() || "";
    const genericTitle = ["yuke", "untitled session", "new chat", current?.session.root.split("/").pop()?.toLowerCase() || ""].includes(nativeTitle.toLowerCase());
    const title = (!genericTitle && nativeTitle) || pane?.title || nativeTitle || current?.session.name || "Untitled chat";
    const presence = snapshot.states[id] || "unknown";
    const native = nativeStates.get(id);
    let label = "unavailable";
    let running = false;
    if (presence === "closed") label = "closed";
    else if (native) {
      label = native.state.type.replaceAll("_", " ") + " · here";
      running = native.state.type !== "idle";
    } else if (directPane) {
      label = directPane.state + " · Herdr";
      running = directPane.state === "working";
    } else if (current) {
      label = current.activity.state.type.replaceAll("_", " ") + (child ? " · child" : " · this engine");
      running = current.activity.state.type !== "idle";
    }
    observed.set(id, { label, running, ownerLabel, title, model: current?.session.model || "", parent: current?.session.origin.type === "child" ? current.session.origin.site.session_id : "", presence });
  }
  return observed;
}
