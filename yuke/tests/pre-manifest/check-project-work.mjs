#!/usr/bin/env node
import assert from "node:assert/strict";
import { exec as shell } from "node:child_process";
import { mkdtemp, mkdir, readFile, copyFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { promisify } from "node:util";
import path from "node:path";

const root = await mkdtemp(path.join(tmpdir(), "yuke-work-'tools-"));
const tools = new Map();
const hooks = new Map();
const listeners = new Map();
const cleanup = [];
let launches = 0;
let barrier = Promise.resolve();
try {
  const config = path.join(root, "config", "yuke", "plugins");
  const workspace = path.join(root, "project");
  await mkdir(config, { recursive: true });
  await mkdir(workspace);
  await copyFile(new URL("../plugins/project-work-store.py", import.meta.url), path.join(config, "project-work-store.py"));
  const variables = { HOME: root, XDG_CONFIG_HOME: path.join(root, "config"), XDG_STATE_HOME: path.join(root, "state") };
  const client = { sessionGet: async (session) => ({ session: { root: workspace, origin: { type: session === "child" ? "child" : "root" } } }) };
  globalThis.workTest = {
    readGitHub: async (helper, root, args, signal) => {
      assert.equal(root, workspace); assert.equal(signal.aborted, false);
      return args.action === "get" ? { item: { url: "https://github.com/example/repo/issues/17" } } : { items: [], repo: "example/repo" };
    },
    client, env: { get: (name) => variables[name] }, fs: { stat: async () => ({ path: workspace }) }, ui: {},
    Window: class { constructor(opts) { this.opts = opts; } },
    WorkDashboard: class { async refresh() {} },
    exec: async (command, options) => {
      launches++;
      await barrier;
      let result;
      try { result = { ...await promisify(shell)(command), code: 0 }; }
      catch (error) { result = { stdout: error.stdout, stderr: error.stderr, code: error.code }; }
      options.onOutput(result.stdout + result.stderr);
      return result;
    },
  };
  let source = await readFile(new URL("../plugins/project-work.js", import.meta.url), "utf8");
  source = source.replace('import { client, env, exec, fs } from "yuke";', 'const { client, env, exec, fs } = globalThis.workTest;')
    .replace('import { currentEntry, currentPane, currentSession, showSession } from "yuke:session";', 'const currentEntry = () => null, currentPane = () => globalThis.workTest.pane || null, currentSession = () => currentPane()?.session, showSession = () => {};')
    .replace('import { ui, Window } from "yuke:ui";', 'const { ui, Window } = globalThis.workTest;')
    .replace('import { WorkDashboard } from "./project-work-view.js";', 'const { WorkDashboard } = globalThis.workTest;')
    .replace('import { readGitHub } from "./project-work-github.js";', 'const { readGitHub } = globalThis.workTest;')
    .replace('import { focusHerdrSession, herdrSessionPanes } from "./herdr.js";', 'const focusHerdrSession = () => {}, herdrSessionPanes = () => new Map();');
  const { projectWork } = await import("data:text/javascript;base64," + Buffer.from(source).toString("base64"));
  const ctx = { alive: true, signal: { aborted: false }, own: (fn) => cleanup.push(fn),
    hook: (name, fn) => hooks.set(name, fn), on: (name, fn) => listeners.set(name, fn), inject() {},
    print: (...args) => { throw new Error(args.join(" ")); }, tools: { define: (tool) => tools.set(tool.name, tool) } };
  projectWork.apply(ctx);
  const call = async (args, sessionId = "source", partId = 1, signal = { aborted: false }) => JSON.parse(
    await tools.get("project_work").execute(args, signal, { workspaceRoot: workspace, sessionId, messageId: 1, partId }));
  const sections = [{ key: "base", text: "Keep me" }];
  const built = hooks.get("prompt.build")({ sections });
  assert.deepEqual(built.replace.sections[0], sections[0]);
  assert.equal(sections.length, 1);
  assert.match(built.replace.sections[1].text, /after meaningful progress/);
  assert.ok(tools.has("github_work"));
  const githubCall = async (args) => JSON.parse(await tools.get("github_work").execute(args, { aborted: false }, { workspaceRoot: workspace, sessionId: "source" }));
  for (const args of [{ action: "close" }, { action: "list", root: "/" }, { action: "list", repo: "foreign/repo" }]) await assert.rejects(githubCall(args));
  const task = { action: "task", title: "Fix user's navigation", status: "later", notes: "Run the suite; 日本語", github_url: "https://github.com/example/repo/issues/17" };
  const saved = await call(task);
  assert.equal((await githubCall({ action: "get", number: 17 })).linked_tasks[0].id, saved.id);
  assert.equal((await call(task)).id, saved.id, "tool replay must retain task identity");
  assert.equal((await call({ action: "list" }, "other-session")).tasks[0].notes, task.notes);
  const checkpoint = { action: "checkpoint", task_id: saved.id, summary: "Focused test passes", next_step: "Run full suite", verification: "Full suite has not run" };
  await call(checkpoint);
  assert.equal((await call({ action: "get", id: saved.id })).checkpoint.session, "source");
  listeners.get("run.started")({ type: "session", session: "source", facts: ["run.started"] });
  await cleanup[0]();
  assert.equal((await call({ action: "list" })).checkpoints[0].stale, 1);
  const beforeChild = launches;
  listeners.get("run.started")({ type: "session", session: "child", facts: ["run.started"] });
  await cleanup[0]();
  assert.equal(launches, beforeChild, "child runs must not invalidate a root checkpoint");
  await call({ action: "context", goal: "Reliable navigation", notes: "Keep global keys", version: 0 });
  await assert.rejects(call({ action: "context", goal: "Lost edit", notes: "", version: 0 }), /refresh/);
  await call({ ...task, id: saved.id, version: 1, status: "now" });
  await assert.rejects(call({ ...task, id: saved.id, version: 1, status: "done" }), /refresh/);
  for (const invalid of [null, [], {}, { action: "activity" }, { action: "list", root: "/" },
    { action: "list", session: "foreign" }, { action: "list", unexpected: true }, { action: "checkpoint" },
    { action: "task", title: "Untyped defaults" }]) await assert.rejects(call(invalid));
  const beforeCancel = launches;
  await assert.rejects(call(task, "source", 20, { aborted: true }), /canceled/);
  assert.equal(launches, beforeCancel, "canceled calls must not launch the store");
  let release;
  barrier = new Promise((resolve) => { release = resolve; });
  const first = call({ ...task, title: "First queued task" }, "source", 30);
  await new Promise((resolve) => setImmediate(resolve));
  const signal = { aborted: false };
  const second = call({ ...task, title: "Canceled queued task" }, "source", 31, signal);
  signal.aborted = true;
  const rejected = assert.rejects(second, /canceled/);
  release();
  await first;
  await rejected;
  const snapshot = await call({ action: "list" });
  assert.equal(snapshot.tasks.length, 2);
  assert.ok(!snapshot.tasks.some((task) => task.title === "Canceled queued task"));
  const commands = new Map();
  const notices = [];
  const uiCleanup = [];
  let shown = 0;
  globalThis.workTest.pane = { session: { sessionId: null } };
  const c = { alive: true, signal: ctx.signal, background: "dark", colors: "truecolor", on() {}, own: (fn) => uiCleanup.push(fn),
    interaction: { notify: (message) => notices.push(message) },
    tui: { style: { set: () => () => {}, palette: {} }, command: { add: (name, spec) => commands.set(name, spec) },
      overlay: (win, onClose) => { shown++; queueMicrotask(onClose); return () => {}; } } };
  projectWork.apply({ ...ctx, own: (fn) => uiCleanup.push(fn), on() {}, tools: { define() {} }, inject: (_, apply) => apply(c) });
  let releaseLocation;
  globalThis.workTest.fs.stat = () => new Promise((resolve) => { releaseLocation = resolve; });
  commands.get("work").run();
  globalThis.workTest.pane = { session: { sessionId: null } };
  releaseLocation({ path: workspace });
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(shown, 0, "a pending project lookup must not open over a different pane");
  assert.ok(notices.some((message) => /pane changed/i.test(message)));
  for (const release of uiCleanup) await release();
  ctx.alive = false;
  await assert.rejects(call(task, "source", 40), /canceled/);
  await cleanup[0]();
  console.log("Project work tool checks passed (real storage, quoting, replay, stale checkpoints, conflicts, cancellation)");
} finally {
  await rm(root, { recursive: true, force: true });
  delete globalThis.workTest;
}
