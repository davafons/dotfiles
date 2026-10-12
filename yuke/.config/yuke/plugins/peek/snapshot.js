import { client } from "yuke";

/** @typedef {{ sessionId: string, capturedAt: number, activity: string, evidence: string, omitted: boolean }} Snapshot */

/** Capture bounded excerpts from an open session without input, writes, or awaits. Null means the session is not open. Read failures throw. @param {string} sessionId @returns {Snapshot | null} */
export function capture(sessionId) {
  const outline = client.sessionOutline(sessionId);
  if (!outline) return null;
  const activity = client.sessionActivity(sessionId);
  const messages = outline.messages;
  const selected = new Set();
  let evidence = "";
  let omitted = false;

  /** @param {number} id @param {string} role @param {number} allowance @param {boolean} [skill] */
  function take(id, role, allowance, skill = false) {
    if (selected.has(id)) return;
    if (evidence.length >= 8000) { omitted = true; return; }
    selected.add(id);
    const parts = client.sessionParts(sessionId, id);
    let body = "";
    for (let i = skill ? 1 : 0; i < parts.length; i++) {
      const part = parts[i];
      if (!part) continue;
      if ("cut" in part || part.type === "reasoning" || part.type === "image" || part.type === "audio" || part.type === "file") omitted = true;
      let value = "";
      if (part.type === "text") value = part.text;
      else if (part.type === "tool") {
        value = "Tool " + part.name + ": " + part.arguments.slice(0, 600) + "\nState: " + part.state.type;
        if (part.arguments.length > 600) omitted = true;
        if (part.state.type === "completed") {
          if (part.state.output.length > 1200) omitted = true;
          value += "\nOutput excerpt: " + part.state.output.slice(0, 1200);
        }
        else if (part.state.type === "error") value += "\nError: " + part.state.error;
      }
      if (!value) continue;
      const room = allowance - body.length;
      if (room <= 0) { omitted = true; break; }
      if (value.length > room) omitted = true;
      body += value.slice(0, room) + "\n";
    }
    const entry = "\n[" + role + " message " + id + "]\n" + body;
    const room = 8000 - evidence.length;
    if (entry.length > room) omitted = true;
    evidence += entry.slice(0, room);
  }

  for (let i = messages.length - 1; i >= 0; i--) {
    const message = messages[i];
    if (message?.type === "compaction") { take(message.id, "Earlier work summary", 2200); break; }
  }
  for (let i = 0; i < messages.length; i++) {
    const message = messages[i];
    if (message?.type === "user" && (!message.source || message.source.type === "parent_instruction")) { take(message.id, "Task", 1600, !!message.skill_name); break; }
  }
  for (let i = messages.length - 1; i >= 0; i--) {
    const message = messages[i];
    if (message?.type === "user" && (!message.source || message.source.type === "parent_instruction")) { take(message.id, "Latest instruction", 1600, !!message.skill_name); break; }
  }
  if (outline.active) take(outline.active.id, "Live draft, unfinished", 2400);
  for (let i = messages.length - 1, n = 0; i >= 0 && n < 8; i--, n++) {
    const message = messages[i];
    if (message) take(message.id, message.type, 1800, !!message.skill_name);
  }
  if (selected.size < messages.length + (outline.active ? 1 : 0)) omitted = true;
  const state = activity?.state;
  const label = !state ? "Unavailable" : state.type === "running_tool" ? "Running " + state.tool_name
    : state.type === "retrying" ? "Retrying: " + state.message.slice(0, 200) : state.type;
  return { sessionId, capturedAt: Date.now(), activity: label, evidence, omitted };
}
