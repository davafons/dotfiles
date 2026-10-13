//! Capture owned, bounded progress facts without changing the working session.
import { client } from "yuke";

/** @typedef {{path: string, lines: string[]}} FileChange */
/** @typedef {{key: string, name: string, kind: "action" | "check", state: Wire.ToolState["type"], label: string, result: string, exit: number | null, files: FileChange[]}} Action */
/** @typedef {{at: number, statusChanged: boolean, evidenceChanged: boolean, newlyVisible: number, updated: number}} Delta */
/** @typedef {{sessionId: string, capturedAt: number, activity: string, queued: number | null, lastTurn: string | null, evidence: string, actions: Action[], errors: string[], delta: Delta | null, omitted: boolean}} Snapshot */

/** Capture bounded transcript facts and recorded diff excerpts. Null means the session is not open. Native read failures throw. The snapshot owns its arrays and strings. @param {string} sessionId @param {Snapshot | null} [previous] @returns {Snapshot | null} */
export function capture(sessionId, previous = null) {
  const outline = client.sessionOutline(sessionId);
  if (!outline) return null;
  const activity = client.sessionActivity(sessionId);
  const outcome = client.sessionLastRun(sessionId);
  const lastTurn = !outcome ? null : (outcome.type === "failed" ? "failed · " + outcome.code + ": " + outcome.message : outcome.type === "turn" ? "ended · " + outcome.finish : outcome.type).slice(0, 240);
  const messages = outline.messages;
  const selected = new Set();
  let evidence = "";
  let omitted = false;
  let fileBudget = 6;
  /** @type {Action[]} */
  const actions = [];
  /** @type {string[]} */
  const errors = [];

  /** @param {number} id @param {string} role @param {number} allowance @param {boolean} [skill] */
  function take(id, role, allowance, skill = false) {
    if (selected.has(id)) return;
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
        const state = part.state;
        if (actions.length < 12) {
          /** @type {Record<string, unknown>} */
          let args = {};
          if (part.arguments.length <= 16384) {
            try {
              const parsed = JSON.parse(part.arguments);
              if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) args = parsed;
            } catch { args = {}; }
          }
          const command = typeof args.command === "string" ? args.command : "";
          const path = typeof args.path === "string" ? args.path : "";
          const result = state.type === "completed" ? state.output : state.type === "running" ? state.output || "" : state.type === "error" ? state.error : "";
          const footer = part.name === "exec" && state.type === "completed" ? /(?:^|\n)\[exit code: (-?\d+)\]\s*$/.exec(result.slice(-80)) : null;
          /** @type {FileChange[]} */
          const files = [];
          if (state.type === "completed" && state.diff) {
            for (let f = 0; f < state.diff.length; f++) {
              if (!fileBudget || files.length === 2) { omitted = true; break; }
              const file = state.diff[f];
              if (!file) continue;
              fileBudget--;
              const lines = file.hunks[0]?.lines || [];
              const shown = [];
              for (let l = 0; l < Math.min(4, lines.length); l++) shown.push((lines[l] || "").slice(0, 120));
              files.push({ path: file.path.slice(0, 200), lines: shown });
              if (file.path.length > 200 || file.hunks.length > 1 || lines.length > 4) omitted = true;
            }
          }
          actions.push({ key: id + ":" + part.id, name: part.name.slice(0, 80),
            kind: part.name === "exec" && /(?:^|[;&|])\s*(?:zig\s+build\s+(?:test|check)|bun\s+test|(?:npm|pnpm)\s+(?:run\s+)?(?:test|check)|mise\s+run\s+(?:test|check|types)|(?:python3?\s+-m\s+)?pytest|cargo\s+test|go\s+test|tsc\b)/.test(command) ? "check" : "action",
            state: state.type, label: (command || path || part.name).slice(0, 240), result: result.slice(-240), exit: footer ? Number(footer[1]) : null, files });
          if (part.name.length > 80 || result.length > 240 || command.length > 240 || path.length > 240) omitted = true;
        } else omitted = true;
        value = "Tool " + part.name + ": " + part.arguments.slice(0, 600) + "\nState: " + state.type;
        if (part.arguments.length > 600) omitted = true;
        if (state.type === "completed") {
          if (state.output.length > 1200) omitted = true;
          value += "\nOutput excerpt: " + state.output.slice(0, 1200);
        } else if (state.type === "error") value += "\nError: " + state.error;
      }
      if (!value) continue;
      const room = allowance - body.length;
      if (room <= 0) { omitted = true; continue; }
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
    if (!message) continue;
    if (message.error && errors.length < 3) errors.push("Message " + message.id + ": " + message.error.message.slice(0, 240));
    take(message.id, message.type, 1800, !!message.skill_name);
  }
  if (selected.size < messages.length + (outline.active ? 1 : 0)) omitted = true;
  const state = activity?.state;
  const queued = activity?.queued ?? null;
  const label = (!state ? "Unavailable" : state.type === "running_tool" ? "Running " + state.tool_name
    : state.type === "retrying" ? "Retrying: " + state.message.slice(0, 200) : state.type).slice(0, 240);
  /** @type {Delta | null} */
  let delta = null;
  if (previous && previous.sessionId === sessionId) {
    const before = new Map(previous.actions.map(action => [action.key, action]));
    let newlyVisible = 0, updated = 0;
    for (let i = 0; i < actions.length; i++) {
      const action = actions[i];
      if (!action) continue;
      const old = before.get(action.key);
      if (!old) newlyVisible++;
      else if (JSON.stringify(old) !== JSON.stringify(action)) updated++;
    }
    delta = { at: previous.capturedAt, statusChanged: previous.activity !== label || previous.queued !== queued || previous.lastTurn !== lastTurn, evidenceChanged: previous.evidence !== evidence, newlyVisible, updated };
  }
  return { sessionId, capturedAt: Date.now(), activity: label, queued, lastTurn, evidence, actions, errors, delta, omitted };
}

/** Format a frozen snapshot's bounded facts outside drawing. No null input is accepted. The caller owns the text. Allocation failures throw. @param {Snapshot} snapshot */
export function describe(snapshot) {
  /** @param {string} value */
  const inline = value => "`" + value.replace(/[\x00-\x1f\x7f`]/g, " ") + "`";
  const lines = ["## Captured progress", "Activity: " + inline(snapshot.activity) + ". Queued inputs: " + (snapshot.queued == null ? "unknown" : snapshot.queued) + ".",
    "Last completed turn: " + (snapshot.lastTurn == null ? "none recorded" : inline(snapshot.lastTurn)) + ".",
    "Limited transcript excerpts. Recorded changes are not the current worktree state."];
  if (snapshot.delta) {
    const delta = snapshot.delta;
    lines.push("", "### Since previous refresh", delta.newlyVisible + " newly visible actions; " + delta.updated + " updated actions.",
      "Activity, queue, or completed-turn outcome " + (delta.statusChanged ? "changed" : "unchanged") + "; captured transcript " + (delta.evidenceChanged ? "changed" : "unchanged") + ".");
  }
  lines.push("", "### Check commands", "Exit codes describe the whole shell command, not each test.");
  let checks = 0;
  for (let i = 0; i < snapshot.actions.length; i++) {
    const action = snapshot.actions[i];
    if (!action || action.kind !== "check") continue;
    checks++;
    lines.push("- " + inline(action.label) + " · " + (action.exit == null ? action.state + "; exit not available" : "exit " + action.exit + " reported") + " · " + inline(action.key));
  }
  if (!checks) lines.push("No recognized check command in these excerpts. Test status is unknown.");
  lines.push("", "### Recorded file changes");
  let files = 0;
  for (let i = 0; i < snapshot.actions.length; i++) {
    const action = snapshot.actions[i];
    if (!action) continue;
    for (let f = 0; f < action.files.length; f++) {
      const file = action.files[f];
      if (!file) continue;
      files++;
      lines.push("- " + inline(file.path) + " · " + inline(action.key) + " · diff excerpt");
      for (let l = 0; l < file.lines.length; l++) lines.push("  - " + inline(file.lines[l] || ""));
    }
  }
  if (!files) lines.push("No recorded diff in these excerpts. File changes are unknown.");
  lines.push("", "### Recent tool actions", "A completed tool call does not mean the task is finished.");
  for (let i = 0; i < snapshot.actions.length; i++) {
    const action = snapshot.actions[i];
    if (!action) continue;
    lines.push("- " + inline(action.name) + " · " + action.state + " · " + inline(action.label) + " · " + inline(action.key));
    if (action.state === "error" && action.result) lines.push("  " + inline(action.result));
  }
  if (!snapshot.actions.length) lines.push("No tool action in these excerpts.");
  if (snapshot.errors.length) {
    lines.push("", "### Reported errors");
    for (let i = 0; i < snapshot.errors.length; i++) lines.push("- " + inline(snapshot.errors[i] || ""));
  }
  if (snapshot.omitted) lines.push("", "Some history, output, or diff lines are omitted. Missing evidence stays unknown.");
  return lines.join("\n");
}
