#!/usr/bin/env node
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

let clips = 0;
let wraps = 0;
let reads = 0;
let detailReads = 0;
let githubReads = 0;
let githubDetailReads = 0;
const pending = new Map();
const painted = [];
globalThis.workViewTest = {
  clip: (value, width) => { clips++; return value.slice(0, Math.max(0, width)); },
  measure: (value) => value.length,
  text: (x, y, value, group) => painted.push({ x, y, value, group }),
  fill() {}, keys: { strokeOf: (event) => event.stroke }, Window: class {},
  wrapRows: (value, width) => {
    wraps++;
    return value.split("\n").flatMap((line) => {
      const rows = [];
      for (let i = 0; i < line.length; i += width) rows.push({ text: line.slice(i, i + width) });
      return rows;
    });
  },
};
let source = await readFile(new URL("../.config/yuke/plugins/project-work/project-work-view.js", import.meta.url), "utf8");
source = source.replace('import { clip, fill, keys, measure, text, Window } from "yuke:ui";', 'const { clip, fill, keys, measure, text, Window } = globalThis.workViewTest;')
  .replace('import { wrapRows } from "yuke:chat";', 'const { wrapRows } = globalThis.workViewTest;');
const { WorkDashboard } = await import("data:text/javascript;base64," + Buffer.from(source).toString("base64"));
const tasks = [
  { id: "active", title: "Active work", status: "now", notes: "Verify the suite", session: "active-session", root: "/project", version: 1 },
  { id: "deferred", title: "Deferred work", status: "later", notes: "Do this later", session: "deferred-session", root: "/project", version: 1 },
];
const data = { name: "project", root: "/project", context: { goal: "Restore project context", notes: "Keep the key handler", version: 1 },
  tasks, counts: [1, 1, 0, 0, 0], offsets: [0, 0, 0, 0, 0], query: "", include_done: false, checkpoints: [] };
const githubItems = [1, 2].map((number) => ({ number, title: "Issue " + number, url: "https://github.com/example/repo/issues/" + number,
  state: "OPEN", author: "tester", labels: [], kind: "issues", draft: false, ci: null, review: null, body: "Read-only body", checks: [] }));
const actions = {
  githubRead: async () => { githubReads++; return { repo: "example/repo", kind: "issues", state: "open", items: githubItems, total: 2, has_next: false }; },
  githubDetail: (args) => { githubDetailReads++; return new Promise((resolve) => pending.set("gh-" + args.number, resolve)); },
  read: async () => { reads++; return data; },
  detail: (id) => { detailReads++; return new Promise((resolve) => pending.set(id, resolve)); },
  action: async () => {},
};
const view = new WorkDashboard({ tui: { root: { invalidatePaint() {} } } }, actions);
view.layout({ x: 0, y: 0, w: 160, h: 45 });
await view.refresh();
assert.equal(view.selectedTask().id, "active");
view.moveColumn(1);
pending.get("active")({ task: tasks[0], checkpoint: { summary: "OLD DETAIL MUST NOT SHOW" } });
await Promise.resolve();
assert.equal(view.detail, null, "an old selection's detail must not replace the new selection");
pending.get("deferred")({ task: tasks[1], checkpoint: null });
await Promise.resolve();
assert.equal(view.detail.task.id, "deferred");
const explanation = view.spans.find((span) => span.value.includes("SELECTED TASK"));
assert.ok(explanation.y > Math.max(...view.blocks.map((block) => block.y + block.h)), "the selected task explanation must sit below all kanban cards, even on a wide terminal");
assert.ok(explanation.x < 5, "the explanation must start below the board, not in a right sidebar");
const spans = view.spans;
const blocks = view.blocks;
const before = { clips, wraps, reads, detailReads };
for (let i = 0; i < 100; i++) view.draw();
assert.deepEqual({ clips, wraps, reads, detailReads }, before, "repaints must not wrap, clip, rebuild, or read storage");
assert.equal(view.spans, spans);
assert.equal(view.blocks, blocks);
assert.ok(painted.some((span) => span.value.includes("Deferred work")));
assert.ok(!painted.some((span) => span.value.includes("OLD DETAIL")));
data.checkpoints = [{ session: "source", root: "/project", updated: Date.now(), stale: 1, summary: "Last progress", next_step: "Next action", verification: "Not run" }];
view.selectTab(2);
const checkpointExplanation = view.spans.find((span) => span.value === "WHERE YOU STOPPED");
assert.ok(checkpointExplanation.y > Math.max(...view.blocks.map((block) => block.y + block.h)), "checkpoint explanations must also sit below their cards");
view.selectTab(3);
await new Promise((resolve) => setImmediate(resolve));
view.move(1);
assert.equal(githubDetailReads, 1, "rapid selection changes must coalesce behind one pending GitHub detail read");
pending.get("gh-1")({ item: githubItems[0], linked_tasks: [], linked_task_count: 0 });
await new Promise((resolve) => setImmediate(resolve));
assert.equal(view.githubDetail, null, "old GitHub details must not replace the current selection");
assert.equal(githubDetailReads, 2);
pending.get("gh-2")({ item: githubItems[1], linked_tasks: [], linked_task_count: 0 });
await new Promise((resolve) => setImmediate(resolve));
assert.equal(view.githubDetail.item.number, 2);
const githubCache = view.spans;
const githubBefore = { clips, wraps, githubReads, githubDetailReads };
for (let i = 0; i < 100; i++) view.draw();
assert.deepEqual({ clips, wraps, githubReads, githubDetailReads }, githubBefore, "GitHub repaints must use cached text and never fetch or rebuild");
assert.equal(view.spans, githubCache);
view.selectTab(0);
for (const bounds of [{ x: 0, y: 0, w: 50, h: 24 }, { x: 0, y: 0, w: 20, h: 8 }]) {
  view.layout(bounds);
  for (const block of view.blocks) {
    assert.ok(block.w >= 0 && block.h >= 0 && block.x + block.w <= bounds.w && block.y + block.h <= bounds.h);
  }
  for (const span of view.spans) assert.ok(span.x + span.value.length <= bounds.w && span.y < bounds.h);
}
view.closed = true;
const closedCache = view.spans;
view.rebuild();
assert.equal(view.spans, closedCache, "late updates must not rebuild a closed view");
console.log("Project work view checks passed (paint cache, out-of-order detail, narrow bounds, closed lifecycle)");
delete globalThis.workViewTest;

let activityCalls = 0;
const liveView = new WorkDashboard({ tui: { root: { invalidatePaint() {} } } }, {
  ...actions, detail: async id => ({task: tasks.find(task => task.id === id), checkpoint: null}),
  activityRead: async () => { activityCalls++; return new Map([["active-session", {label: "working · Herdr", running: true}]]); },
});
liveView.layout({x:0,y:0,w:160,h:45});
await liveView.refresh();
await liveView.refreshActivity();
assert.ok(liveView.spans.some(span => span.value.includes("working · Herdr")), "cards must show observed live activity");
const liveSpans = liveView.spans;
const liveBefore = {clips, wraps, activityCalls};
liveView.animate();
liveView.draw();
assert.equal(liveView.spans, liveSpans, "animation must retain its paint cache");
assert.deepEqual({clips, wraps, activityCalls}, liveBefore, "animation and draw must not clip, wrap or fetch");
liveView.actions.activityRead = async () => new Map([["active-session", {label: "idle · here", running: false}]]);
await liveView.refreshActivity();
assert.equal(tasks[0].status, "now", "idle must not mark a task done");
assert.ok(liveView.spans.some(span => span.value.includes("idle · here")));
assert.equal(liveView.animatedSpans.length, 0);
let resolveActivity;
liveView.actions.activityRead = () => new Promise(resolve => { resolveActivity = resolve; });
const late = liveView.refreshActivity();
liveView.closed = true;
resolveActivity(new Map([["active-session", {label:"late working",running:true}]]));
await late;
assert.ok(!liveView.spans.some(span => span.value.includes("late working")), "close must reject stale activity results");
console.log("Live activity and allocation-free animation guards passed");

const originalOwner = tasks[0].session;
liveView.closed = false;
data.checkpoints = [{task_id: "active", session: "latest-session", root: "/project"}];
liveView.detail = null;
let linkedIds;
liveView.actions.activityRead = async ids => { linkedIds = ids; return new Map(); };
await liveView.refreshActivity();
assert.deepEqual(linkedIds, ["latest-session", "deferred-session"], "activity must follow a task's latest checkpoint session");
assert.equal(tasks[0].session, originalOwner, "observing a checkpoint must not change the recorded task owner");

const nativeReads = [];
globalThis.workActivityTest = {
  client: {sessionActivity(id) { nativeReads.push(id); if (id === "local") return {state: {type: "idle"}}; if (id === "missing") throw Error("missing session"); return null; }},
  remote: async () => new Map([["local", "working"], ["remote", "working"], ["blocked", "blocked"]]),
};
let activitySource = await readFile(new URL("../.config/yuke/plugins/project-work/activity.js", import.meta.url), "utf8");
activitySource = activitySource.replace('import { client } from "yuke";', 'const {client} = globalThis.workActivityTest;')
  .replace('import { herdrSessionStates } from "../herdr/index.js";', 'const herdrSessionStates = (...args) => globalThis.workActivityTest.remote(...args);');
const {readActivity} = await import("data:text/javascript;base64," + Buffer.from(activitySource).toString("base64"));
const signal = {aborted: false};
const observations = await readActivity(["local", "remote", "blocked", "missing", "local", ""], signal);
assert.deepEqual([...observations], [
  ["local", {label: "idle · here", running: false}],
  ["remote", {label: "working · Herdr", running: true}],
  ["blocked", {label: "blocked · Herdr", running: false}],
  ["missing", {label: "unavailable", running: false}],
], "native activity wins; unavailable never means idle; only remote working animates");
assert.deepEqual(nativeReads, ["local", "remote", "blocked", "missing"], "duplicate and empty links must not cause native reads");
globalThis.workActivityTest.remote = async () => { throw Error("offline"); };
assert.deepEqual([...await readActivity(["local", "remote"], signal)], [
  ["local", {label: "idle · here", running: false}], ["remote", {label: "unavailable", running: false}],
], "a remote failure must preserve local truth and not invent idle");
nativeReads.length = 0;
signal.aborted = true;
assert.equal((await readActivity(["local"], signal)).size, 0);
assert.deepEqual(nativeReads, [], "cancellation must prevent native reads");
delete globalThis.workActivityTest;
console.log("Linked checkpoint, native precedence, unavailable, and cancellation guards passed");
