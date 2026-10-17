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
  wrapRows: (value, width) => { wraps++; return value.split("\n").flatMap(line => {
    const rows = [];
    for (let i = 0; i < line.length; i += width) rows.push({text: line.slice(i, i + width)});
    return rows;
  }); },
  Document: class {
    setText(value) { this.value = value; }
    rows(width) {
      wraps++;
      return this.value.split("\n").flatMap(line => {
        if (!line) return [{ segments: [] }];
        const rows = [];
        for (let i = 0; i < line.length; i += width) rows.push({ segments: [{ text: line.slice(i, i + width), group: "MdTest" }] });
        return rows;
      });
    }
  },
};
let source = await readFile(new URL("../.config/yuke/plugins/project-work/project-work-view.js", import.meta.url), "utf8");
source = source.replace('import { clip, fill, keys, measure, text, Window, Document } from "yuke:ui";', 'const { clip, fill, keys, measure, text, Window, Document } = globalThis.workViewTest;').replace('import { wrapRows } from "yuke:chat";', 'const { wrapRows } = globalThis.workViewTest;');
const { WorkDashboard, SessionTaskIndicator } = await import("data:text/javascript;base64," + Buffer.from(source).toString("base64"));
const tasks = [
  { id: "active", title: "Active work", status: "now", notes: "Verify the suite", session: "active-session", owner_session:"active-session", root: "/project", version: 1 },
  { id: "deferred", title: "Deferred work", status: "later", notes: "Do this later", session: "deferred-session", owner_session:"deferred-session", root: "/project", version: 1 },
];
const data = { name: "project", root: "/project",
  tasks, counts: [1, 1, 0, 0, 0], offsets: [0, 0, 0, 0, 0], query: "", include_done: false };
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
assert.deepEqual(view.spans.filter(span => span.y === 1).map(span => span.value.trim()), ["1 Board", "2 GitHub"], "work has only the board and GitHub tabs");
assert.ok(!view.spans.some(span => /context|handoff|checkpoint|shared goal/i.test(span.value)), "removed features must not appear in headers or controls");
view.moveColumn(1);
pending.get("active")({ task: tasks[0], checkpoint: { summary: "OLD DETAIL MUST NOT SHOW" } });
await Promise.resolve();
assert.equal(view.detail, null, "an old selection's detail must not replace the new selection");
pending.get("deferred")({ task: tasks[1] });
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
assert.ok(painted.some(span => span.group === "MdTest"), "details must retain Markdown segment styling rather than flattening it");
view.onKey({type:"key",event:"press",stroke:"2"});
assert.equal(view.tab, 1, "2 opens GitHub directly");
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
view.onKey({type:"key",event:"press",stroke:"tab"});
assert.equal(view.tab, 0, "Tab wraps from GitHub to Board");
view.onKey({type:"key",event:"press",stroke:"shift+tab"});
assert.equal(view.tab, 1, "Shift-Tab wraps from Board to GitHub");
view.onKey({type:"key",event:"press",stroke:"1"});
const retiredActions = [];
view.actions.action = async name => { retiredActions.push(name); };
for (const stroke of ["c", "g", "3", "4"]) view.onKey({type:"key",event:"press",stroke});
assert.equal(view.tab, 0, "retired tab numbers must not navigate");
assert.deepEqual(retiredActions, [], "retired shortcuts must not invoke actions");
view.inspect();
assert.ok(!view.spans.some(span => /handoff|checkpoint/i.test(span.value)), "the inspector must have no checkpoint action or handoff details");
view.onKey({type:"key",event:"press",stroke:"esc"});
const githubTab = view.hits.find(hit => hit.kind === "tab" && hit.index === 1);
view.onMouse({event:"press",button:"left",col:githubTab.x,row:githubTab.y,count:1});
assert.equal(view.tab, 1, "mouse selection opens the second GitHub tab");
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


let activityCalls = 0;
const liveView = new WorkDashboard({ tui: { root: { invalidatePaint() {} } } }, {
  ...actions, detail: async id => ({task: tasks.find(task => task.id === id)}),
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
assert.deepEqual(linkedIds, ["active-session", "deferred-session"], "legacy checkpoint data must not redirect task navigation or activity");
assert.equal(tasks[0].session, originalOwner, "observing activity must not change the recorded source session");

const nativeReads = [];
const sessionIds = {local:"a".repeat(32), remote:"b".repeat(32), blocked:"c".repeat(32), missing:"d".repeat(32), child:"e".repeat(32), parent:"f".repeat(32)};
const nativeItems = new Map(Object.entries(sessionIds).filter(([key]) => key !== "missing").map(([key,id]) => [id, {
  session:{id, root:"/project", title: key + " chat", model:"fixture/model", origin:key === "child" ? {type:"child",site:{session_id:sessionIds.parent}} : {type:"root"}, ...(key === "child" ? {name:"reviewer"} : {})},
  activity:{state:{type:key === "child" ? "running_tool" : "idle"}},
}]));
globalThis.workActivityTest = {children:{id:(name,id) => name + "-" + id.slice(-8)},client:{
  sessionGet: async id => { if (!nativeItems.has(id)) throw Error("missing"); return nativeItems.get(id); },
  sessionActivity(id) { nativeReads.push(id); return id === sessionIds.local ? {state:{type:"idle"}} : null; },
}};
let activitySource = await readFile(new URL("../.config/yuke/plugins/project-work/activity.js", import.meta.url), "utf8");
activitySource = activitySource.replace('import { client, children } from "yuke";', 'const {client,children} = globalThis.workActivityTest;');
const {readActivity} = await import("data:text/javascript;base64," + Buffer.from(activitySource).toString("base64"));
const signal = {aborted:false};
const pane = (number,state) => ({number,title:"Reported chat",pane:"w1:p"+number,workspace:"w1",state});
let requestedRoots;
const probe = async roots => { requestedRoots = roots; return {states:Object.fromEntries(Object.keys(roots).map(id => [id,"open"])), panes:{
  [sessionIds.local]:pane("1","working"), [sessionIds.remote]:pane("2","working"), [sessionIds.blocked]:pane("3","blocked"), [sessionIds.parent]:pane("4","idle"),
}, released:[]}; };
const observations = await readActivity([...Object.values(sessionIds),sessionIds.local,""],signal,probe);
assert.equal(observations.get(sessionIds.local).label,"idle · here", "live native state wins over a reported state");
assert.equal(observations.get(sessionIds.remote).ownerLabel,"Agent 2");
assert.equal(observations.get(sessionIds.remote).title,"remote chat");
assert.equal(observations.get(sessionIds.remote).model,"fixture/model");
assert.equal(observations.get(sessionIds.blocked).running,false);
assert.equal(observations.get(sessionIds.missing).presence,"unknown", "missing metadata cannot prove closure");
assert.equal(observations.get(sessionIds.child).ownerLabel,"Agent 4 / reviewer-eeeeeeee", "child identity uses the actual parent's agent number");
assert.equal(observations.get(sessionIds.child).label,"running tool · child", "an idle parent pane must not hide its active child");
assert.equal(requestedRoots[sessionIds.child],sessionIds.parent, "children probe the native root-tree lock, never a nonexistent child lock");
assert.equal(nativeReads.length,Object.keys(sessionIds).length,"duplicate links must not duplicate native reads");
const unavailable = await readActivity([sessionIds.remote],signal,async () => {throw Error("offline");});
assert.equal(unavailable.get(sessionIds.remote).presence,"unknown", "probe failure must never prove closure");
const closed = await readActivity([sessionIds.remote],signal,async roots => ({states:{[sessionIds.remote]:"closed"},panes:{},released:["task"]}));
assert.equal(closed.get(sessionIds.remote).label,"closed");
assert.equal(closed.get(sessionIds.remote).running,false);
nativeReads.length = 0;
signal.aborted = true;
assert.equal((await readActivity([sessionIds.local],signal,probe)).size,0);
assert.deepEqual(nativeReads,[],"cancellation must prevent native reads");
delete globalThis.workActivityTest;
console.log("Agent identity, native precedence, child tree ownership, unknown/closed and cancellation guards passed");

const many = Array.from({length:12}, (_, i) => ({...tasks[0], id: "paged-" + i, title: "Card " + i}));
const paging = new WorkDashboard({tui: {root: {invalidatePaint() {}}}}, {
  ...actions,
  read: async offsets => ({...data, tasks: many.slice(offsets[0], offsets[0] + 5), counts:[12,0,0,0,0], offsets:[...offsets]}),
  detail: async id => ({task: many.find(task => task.id === id)}),
});
paging.layout({x:0,y:0,w:160,h:45});
await paging.refresh();
assert.ok(paging.spans.some(span => span.value === "1-4/12 ↓"), "range must describe visible cards, not all loaded cards");
paging.move(4);
assert.ok(paging.spans.some(span => span.value === "↑ 2-5/12 ↓"));
paging.move(1);
await new Promise(resolve => setImmediate(resolve));
assert.equal(paging.selectedTask().id, "paged-5", "down at a page boundary must continue into the next page");
assert.ok(paging.spans.some(span => span.value === "↑ 6-9/12 ↓"));
paging.move(-1);
await new Promise(resolve => setImmediate(resolve));
assert.equal(paging.selectedTask().id, "paged-4", "up at the first card must go to the previous page's final card");
paging.page(1);
await new Promise(resolve => setImmediate(resolve));
paging.page(1);
await new Promise(resolve => setImmediate(resolve));
assert.ok(paging.spans.some(span => span.value === "↑ 11-12/12 · end"));
assert.ok(paging.spans.some(span => span.value === "█"), "each nonempty column must have a scrollbar thumb");
paging.inspect();
await new Promise(resolve => setImmediate(resolve));
const rail = paging.spans.find(span => span.value === "TASK ACTIONS");
assert.ok(rail.x > paging.detailRect.x + paging.detailRect.w, "actions must occupy their own right column");
assert.ok(paging.spans.some(span => span.value === "o Assign to this chat"));
paging.onKey({type:"key",event:"press",stroke:"esc"});
assert.equal(paging.taskFocus, null);
const owner = {...many[10], owner_session:"real-owner", owner_root:"/project/preview"};
paging.columns[0][0] = owner;
paging.selected = 0;
paging.activity = new Map([["real-owner", {label:"working", running:true, ownerLabel:"Agent 7", title:"Parallel app checks", model:"fixture/reviewer"}], [owner.session, {label:"working",running:true}]]);
paging.data.owner_counts = {"real-owner":1};
paging.rebuild();
assert.ok(paging.spans.some(span => span.value.includes("Agent 7 · Parallel app checks")), "cards need a real agent number and chat title");
assert.ok(paging.spans.some(span => span.value.includes("One task per session")), "assignment semantics must be explicit");
let opened;
paging.actions.action = async (name, task) => { opened = [name, task.owner_session]; };
let card = paging.hits.find(hit => hit.kind === "card" && hit.index === 0);
paging.onMouse({event:"press",button:"left",col:card.x,row:card.y,count:1});
await new Promise(resolve => setImmediate(resolve));
assert.deepEqual(opened, ["session", "real-owner"], "one click on an active owned card must open its actual owner, not its creator or checkpoint");
opened = null;
paging.columns[0][0] = owner;
paging.activity.set("real-owner", {label:"idle", running:false});
paging.rebuild();
card = paging.hits.find(hit => hit.kind === "card" && hit.index === 0);
paging.onMouse({event:"press",button:"left",col:card.x,row:card.y,count:1});
await new Promise(resolve => setImmediate(resolve));
assert.deepEqual(opened, ["session", "real-owner"], "idle is not a release and must not break owner navigation");
opened = null;
paging.columns[0][0] = {...owner, owner_session:""};
paging.rebuild();
card = paging.hits.find(hit => hit.kind === "card" && hit.index === 0);
paging.onMouse({event:"press",button:"left",col:card.x,row:card.y,count:1});
await new Promise(resolve => setImmediate(resolve));
assert.equal(opened, null, "legacy now cards must never navigate to a guessed owner");
console.log("Viewport ranges, automatic paging, scrollbar, right action rail and owner navigation passed");
const legacyTask = {...tasks[0], id:"legacy-unclaimed", owner_session:"", owner_root:""};
const legacyView = new WorkDashboard({tui:{root:{invalidatePaint(){}}}}, {
  ...actions,
  read: async () => ({...data, tasks:[legacyTask], counts:[1,0,0,0,0]}),
  detail: async () => ({task:legacyTask}),
  activityRead: async () => new Map([[legacyTask.session, {label:"working · Herdr", running:true}]]),
});
legacyView.layout({x:0,y:0,w:160,h:45});
await legacyView.refresh();
await legacyView.refreshActivity();
const legacyCard = legacyView.hits.find(hit => hit.kind === "card");
assert.ok(!legacyView.spans.some(span => span.y >= legacyCard.y && span.y < legacyCard.y + legacyCard.h && span.value.includes("working")),
  "a linked working conversation must not make an unclaimed task look active");
assert.equal(legacyView.animatedSpans.length, 0, "unclaimed tasks must not animate as task work");
legacyView.inspect();
await new Promise(resolve => setImmediate(resolve));
assert.ok(!legacyView.spans.some(span => /Open linked|Open assigned|owner|LINKED CHAT/i.test(span.value)), "an unassigned task must not offer creator-chat navigation or activity");
assert.ok(legacyView.spans.some(span => span.value === "o Assign to this chat"));
legacyView.onKey({type:"key",event:"press",stroke:"esc"});
const headers = legacyView.hits.filter(hit => hit.kind === "column");
assert.ok(headers[0].w > headers[1].w * 3, "empty columns must give most of their width to populated columns");
assert.equal(legacyView.column, 0);
legacyView.onKey({type:"key",event:"press",stroke:"z"});
assert.ok(!legacyView.hits.some(hit => hit.kind === "card" && hit.column === 0), "z collapses the selected populated column");
legacyView.onKey({type:"key",event:"press",stroke:"z"});
assert.ok(legacyView.hits.some(hit => hit.kind === "card" && hit.column === 0), "z restores the column's tasks");
legacyView.onMouse({event:"press",button:"left",col:headers[1].x,row:headers[1].y,count:1});
const expandedEmpty = legacyView.hits.find(hit => hit.kind === "column" && hit.column === 1);
assert.ok(expandedEmpty.w > headers[1].w, "clicking a compact column header expands it");
legacyView.onKey({type:"key",event:"press",stroke:"Z"});
assert.ok(legacyView.hits.find(hit => hit.kind === "column" && hit.column === 1).w < expandedEmpty.w, "Z restores automatic empty-column compaction");
for (const bounds of [{x:0,y:0,w:95,h:24}, {x:0,y:0,w:60,h:24}]) {
  legacyView.layout(bounds);
  for (const span of legacyView.spans) assert.ok(span.x + span.value.length <= bounds.w && span.y < bounds.h, "collapsed layouts must remain in bounds");
}
legacyView.layout({x:0,y:0,w:160,h:45});
legacyView.column = 0;
legacyView.columnModes[0] = "collapsed";
legacyView.rebuild();
legacyView.move(1);
legacyView.moveColumn(1);
assert.ok(legacyView.columnCollapsed(0), "scrolling a folded column must not permanently expand it after leaving");
legacyView.moveColumn(-1);
assert.ok(legacyView.columnCollapsed(0), "returning to that column must keep its folded preference");
assert.ok(legacyView.columnLayouts(160).find(column => column.column === 0).w <= 3, "folded rails must use at most four terminal cells including their gap");
legacyView.move(1);
assert.ok(!legacyView.columnCollapsed(0), "browsing tasks can temporarily preview a folded column");
assert.ok(legacyView.footer.includes("z keep open"), "a temporary preview must explain how to pin it open");
legacyView.toggleColumn();
legacyView.moveColumn(1);
assert.ok(!legacyView.columnCollapsed(0), "explicit expansion must pin a temporary preview open after leaving");
legacyView.moveColumn(-1);
assert.ok(!legacyView.columnCollapsed(0), "explicitly expanded columns stay open when revisited");
await legacyView.refresh(true);
legacyView.layout({x:0,y:0,w:95,h:24});
assert.equal(legacyView.columnModes[0], "expanded", "refresh and resize must preserve explicit expansion");
legacyView.layout({x:0,y:0,w:160,h:45});
legacyView.toggleColumn();
legacyView.move(1);
const nextRail = legacyView.columnLayouts(160).find(column => column.column === 1);
legacyView.onMouse({event:"press",button:"wheel_down",col:nextRail.x + 1,row:10,count:1});
assert.ok(legacyView.columnCollapsed(0), "scrolling into another column must dismiss the previous temporary preview");
legacyView.columnModes.fill("auto");
legacyView.selectColumn(0);
legacyView.peekColumn = -1;
legacyView.rebuild();
let finishQuiet;
legacyView.actions.read = () => new Promise(resolve => { finishQuiet = resolve; });
const quietPoll = legacyView.refresh(true);
let quietAction = false;
legacyView.actions.action = async () => { quietAction = true; return "close"; };
await legacyView.act("session");
assert.ok(quietAction, "background polling must not drop a session-navigation click");
finishQuiet({...data, tasks:[legacyTask], counts:[1,0,0,0,0]});
await quietPoll;
console.log("Legacy-task truthfulness, source navigation and automatic/manual column collapse passed");
delete globalThis.workViewTest;

const definitions = new Map();
const hooks = new Map();
let hostSource = await readFile(new URL("../.config/yuke/plugins/project-work/index.js", import.meta.url), "utf8");
globalThis.workHostUI = {SessionTaskIndicator, events:{}, ChatView:class {}};
hostSource = 'const {SessionTaskIndicator, events, ChatView} = globalThis.workHostUI; const env = {get: () => undefined}; const exec = (...args) => globalThis.workHostExec(...args);\n' + hostSource.replace(/^import .*;\n/gm, "");
const {default: installWork} = await import("data:text/javascript;base64," + Buffer.from(hostSource).toString("base64"));
installWork({
  signal: {aborted:false}, alive:true, own() {},
  get: () => null,
  hook: (name, callback) => hooks.set(name, callback),
  tools: {define: definition => definitions.set(definition.name, definition)},
  on: () => assert.fail("headless task bookkeeping must not register activity listeners"),
});
assert.deepEqual([...definitions.keys()], ["project_work", "github_work"]);
const workTool = definitions.get("project_work");
assert.deepEqual(workTool.parameters.properties.action.enum, ["list", "get", "task", "notes", "claim", "release", "message"]);
for (const field of ["task_id", "summary", "next_step", "verification", "goal"]) assert.ok(!(field in workTool.parameters.properties));
const instructions = hooks.get("prompt.build")({sections:[]}).replace.sections[0].text;
assert.ok(!/checkpoint|handoff|project context/i.test(instructions + workTool.description), "agent instructions must not request removed bookkeeping");
assert.ok(instructions.includes("Record failed and unrun checks"), "verification belongs in task notes");
for (const action of ["context", "checkpoint"]) await assert.rejects(workTool.execute({action}, {aborted:false}, {}), /Unknown work action or field/);
assert.deepEqual(definitions.get("github_work").parameters.properties.action.enum, ["list", "get"], "GitHub remains read-only");
console.log("Task-only tool schema, prompt and headless registration checks passed");

let taskOnlyRequests = 0;
globalThis.workHostExec = async (command, options) => {
  assert.ok(command.includes('"api_version":2'), "updated tools must opt into task-only storage responses");
  taskOnlyRequests++;
  options.onOutput(JSON.stringify({tasks:[], owner_counts:{}, total:0, offset:0}));
  return {code:0};
};
assert.deepEqual(JSON.parse(await workTool.execute({action:"list"}, {aborted:false}, {workspaceRoot:"/project", sessionId:"source", messageId:1, partId:1})), {tasks:[], owner_counts:{}, total:0, offset:0});
assert.equal(taskOnlyRequests, 1);
delete globalThis.workHostExec;

const completedTask = {...tasks[0], id:"completed", title:"Completed work", status:"done"};
const visibilityReads = [];
const visibilityView = new WorkDashboard({tui:{root:{invalidatePaint(){}}}}, {
  ...actions,
  read: async (offsets, query, done) => {
    visibilityReads.push(done);
    return {...data, tasks:done ? [...tasks, completedTask] : tasks, counts:[1,1,0,0,1], offsets:[...offsets], include_done:done};
  },
  detail: async id => ({task:[...tasks,completedTask].find(task => task.id === id)}),
});
visibilityView.layout({x:0,y:0,w:160,h:45});
await visibilityView.refresh();
visibilityView.onKey({type:"key",event:"press",stroke:"d"});
await new Promise(resolve => setImmediate(resolve));
assert.equal(visibilityView.includeDone, false, "d must not toggle completed-task visibility");
assert.deepEqual(visibilityReads, [false], "d must not trigger a visibility refresh");
assert.ok(visibilityView.spans.some(span => span.value === "Show done"), "the mouse control must remain available without a hotkey prefix");
visibilityView.selectColumn(4);
visibilityView.toggleColumn();
assert.ok(!visibilityView.spans.some(span => /d: show done|d Show done|d Hide done/.test(span.value)), "empty-column hints must not advertise the retired hotkey");
let visibilityControl = visibilityView.hits.find(hit => hit.action === "done");
visibilityView.onMouse({event:"press",button:"left",col:visibilityControl.x,row:visibilityControl.y,count:1});
await new Promise(resolve => setImmediate(resolve));
assert.equal(visibilityView.includeDone, true);
assert.equal(visibilityView.columns[4][0].id, "completed", "clicking Show done must still load completed tasks");
assert.ok(visibilityView.spans.some(span => span.value === "Hide done"));
visibilityControl = visibilityView.hits.find(hit => hit.action === "done");
visibilityView.onMouse({event:"press",button:"left",col:visibilityControl.x,row:visibilityControl.y,count:1});
await new Promise(resolve => setImmediate(resolve));
assert.equal(visibilityView.includeDone, false);
assert.equal(visibilityView.columns[4].length, 0);
visibilityView.closed = true;
console.log("Completed-task hotkey removed; mouse visibility controls preserved");

const assignmentReads = [];
const assignmentPending = new Map();
let stripChanges = 0;
const strip = new SessionTaskIndicator(id => {
  assignmentReads.push(id);
  return new Promise((resolve, reject) => assignmentPending.set(id, {resolve,reject}));
}, () => { stripChanges++; });
const initialStrip = strip.refresh(["session-a", "session-b"]);
assert.match(strip.row("session-a", 100).text, /reading assignment/);
assignmentPending.get("session-a").resolve({tasks:[{id:"task-a", title:"Build task", status:"now"}], total:1});
assignmentPending.get("session-b").resolve({tasks:[],total:0});
await initialStrip;
assert.equal(strip.row("session-a", 100).text, "Task [now]: Build task · /work");
assert.equal(strip.row("session-b", 100).text, "Task: not assigned · /work to assign");
assert.equal(strip.row(null, 100).text, "Task: not assigned · /work to assign");
const stripReads = assignmentReads.length;
for (let i = 0; i < 100; i++) strip.row("session-a", 20);
assert.equal(assignmentReads.length, stripReads, "strip layout must use cached data, not perform reads");
assert.ok(strip.row("session-a", 20).text.length <= 20);
const failedStrip = strip.refresh(["session-a"]);
assignmentPending.get("session-a").reject(Error("storage offline"));
await failedStrip;
assert.match(strip.row("session-a", 100).text, /assignment unavailable/);
assert.ok(!strip.row("session-a", 100).text.includes("Build task"), "failed reads must not label a stale task as current");
const conflictStrip = strip.refresh(["session-a"]);
assignmentPending.get("session-a").resolve({tasks:[{id:"old-a",title:"Old task",status:"now"}],total:3});
await conflictStrip;
assert.match(strip.row("session-a", 100).text, /3 conflicting assignments/);
const switchingStrip = strip.refresh(["session-a"]);
await strip.refresh([]);
assignmentPending.get("session-a").resolve({tasks:[{id:"old",title:"Late old task",status:"now"}],total:1});
await switchingStrip;
assert.ok(!strip.row("session-a", 100).text.includes("Late old task"), "a removed pane must reject its old pending read");
const closingStrip = strip.refresh(["session-b"]);
strip.close();
const beforeCloseChanges = stripChanges;
assignmentPending.get("session-b").resolve({tasks:[{id:"late",title:"Late after close",status:"now"}],total:1});
await closingStrip;
assert.equal(stripChanges, beforeCloseChanges, "disposal must reject late strip updates");
console.log("Per-session task strip, unavailable/conflict state, narrow bounds, switching and late-result guards passed");

const uiReleases = [];
let stripAdvice;
installWork({
  signal:{aborted:false}, alive:true,
  own: release => uiReleases.push(release),
  get: () => ({root:{root_node:null, invalidate(){}}, style:{set:() => () => {}, palette:{}}, command:{add(){}}}),
  hook(){}, tools:{define(){}}, on(){},
  advise: (target, name, kind, callback) => { if (name === "bail") stripAdvice = callback; },
});
const queuedRow = {text:"Existing queued input", group:"UIDim"};
const combined = stripAdvice(() => [queuedRow], "chat.strip", {session:{sessionId:null},rect:{w:160}});
assert.equal(combined[0], queuedRow, "the task indicator must preserve existing queued and prompt rows");
assert.equal(combined[1].text, "Task: not assigned · /work to assign");
assert.equal(stripAdvice(() => "unchanged", "other.event"), "unchanged");
for (const release of uiReleases.reverse()) await release();
delete globalThis.workHostUI;
console.log("Task strip preserves pre-existing rows and unloads its polling");
