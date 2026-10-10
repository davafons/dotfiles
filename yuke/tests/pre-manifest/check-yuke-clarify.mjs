#!/usr/bin/env node
import assert from "node:assert/strict";
import { exec as shell } from "node:child_process";
import { mkdtemp, mkdir, readFile, copyFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { promisify } from "node:util";
import path from "node:path";

const root = await mkdtemp(path.join(tmpdir(), "yuke-clarify-tools-"));
const tools = new Map();
const hooks = new Map();
const cleanup = [];
const notices = [];
let execBarrier = Promise.resolve();
try {
  const config = path.join(root, "config", "yuke", "plugins");
  await mkdir(config, { recursive: true });
  await copyFile(new URL("../plugins/yuke-clarify-store.py", import.meta.url), path.join(config, "yuke-clarify-store.py"));
  const variables = { HOME: root, XDG_CONFIG_HOME: path.join(root, "config"), XDG_STATE_HOME: path.join(root, "state") };
  globalThis.clarifyTest = {
    client: {}, events: {}, env: { get: (name) => variables[name] },
    exec: async (command) => {
      await execBarrier;
      try { return { ...await promisify(shell)(command), code: 0 }; }
      catch (error) { return { stdout: error.stdout, stderr: error.stderr, code: error.code }; }
    },
  };
  let source = await readFile(new URL("../plugins/yuke-clarify.js", import.meta.url), "utf8");
  source = source.replace('import { client, env, events, exec } from "yuke";', 'const { client, env, events, exec } = globalThis.clarifyTest;')
    .replace('import { currentSession } from "yuke:session";', 'const currentSession = () => null;')
    .replace('import { clip, Composer, List, Pager, Window } from "yuke:ui";', 'const clip = (s) => s, Composer = class {}, List = class {}, Pager = class {}, Window = class {};')
    .replace('import { wrapRows } from "yuke:chat";', 'const wrapRows = () => [];');
  const { yukeClarify, validateQuestion, validateBatch, questionResponse, answerMessage, batchAnswerMessage } = await import("data:text/javascript;base64," + Buffer.from(source).toString("base64"));
  const ctx = { alive: true, own: (fn) => cleanup.push(fn), hook: (name, fn) => hooks.set(name, fn),
    inject: () => {}, tools: { define: (tool) => tools.set(tool.name, tool) },
    interaction: { notify: (...args) => notices.push(args) } };
  yukeClarify.apply(ctx);
  assert.equal(yukeClarify.name, "yuke-clarify");
  assert.deepEqual([...tools.keys()], ["ask_question", "request_user_input"]);
  const call = (args, sessionId = "origin", partId = 1, aborted = false) => tools.get("ask_question").execute(args, { aborted }, { sessionId, messageId: 1, partId });
  const question = { title: "Target", question: "Where should this run?", options: [{ label: "Local", recommended: true }, { label: "Server", description: "Remote access" }] };
  for (const invalid of [null, [], {}, { ...question, title: " " }, { ...question, title: "bad\u001b[31m" },
    { ...question, unknown: true }, { ...question, options: "Local" }, { ...question, options: [{ label: "Local" }, { label: "Local" }] },
    { ...question, options: [{ label: "a", recommended: true }, { label: "b", recommended: true }] },
    { ...question, options: [{ label: "a", recommended: "yes" }] }, { ...question, options: Array(9).fill({ label: "Local" }) }]) {
    await assert.rejects(call(invalid));
  }
  await assert.rejects(call(question, "origin", 1, true), /canceled/);
  const queued = JSON.parse(await call(question));
  assert.equal(queued.status, "pending");
  assert.match(queued.message, /not answered/);
  assert.equal(JSON.parse(await call(question, "origin", 2)).id, queued.id);
  assert.notEqual(JSON.parse(await call(question, "another")).id, queued.id);
  const free = validateQuestion({ title: "Name", question: "What name?" });
  assert.deepEqual(free.options, []);
  const sections = [{ key: "existing", text: "Keep me" }];
  const built = hooks.get("prompt.build")({ sections });
  assert.deepEqual(built.replace.sections[0], sections[0]);
  assert.match(built.replace.sections[1].text, /never guess/);
  assert.equal(sections.length, 1, "must not mutate existing prompt sections");
  const answer = answerMessage({ ...free, id: queued.id, kind: "answered", answer: "My name" });
  assert.match(answer, /User answer: My name/);
  assert.match(answer, /Question: What name\?/);
  assert.match(answerMessage({ ...free, id: queued.id, kind: "dismissed" }), /Do not treat this as approval/);
  assert.equal(validateQuestion(question).multi_select, false);
  await assert.rejects(call({ ...question, multi_select: "yes" }));
  await assert.rejects(call({ title: "Empty", question: "Pick?", multi_select: true }));
  const multi = { ...validateQuestion({ ...question, multi_select: true }), id: "multi", session: "origin", status: "pending" };
  assert.deepEqual(questionResponse(multi, { text: "", selected: 0, other: false }).responses, [], "recommendations are not implicitly checked");
  assert.deepEqual(questionResponse(multi, { text: "Audit too", selected: 1, other: true, otherSelected: true, checked: [1, 0, 1, -1, 20] }).responses,
    ["Local", "Server", "user_note: Audit too"]);
  assert.deepEqual(questionResponse({ ...multi, multi_select: false }, { text: "VPN only", selected: 1, other: false, notes: true }).responses,
    ["Server", "user_note: VPN only"]);
  const batchArgs = { questions: [
    { id: "features", header: "Features", question: "What features?", multi_select: true, options: [{ label: "Logging (Recommended)", description: "Diagnostics" }, { label: "Metrics", description: "Monitoring" }] },
    { id: "owner", header: "Owner", question: "Who owns it?" },
  ] };
  const normalized = validateBatch(batchArgs);
  assert.equal(normalized[0].options[0].label, "Logging");
  assert.equal(normalized[0].options[0].recommended, true);
  for (const invalid of [null, {}, { questions: [] }, { questions: Array(4).fill(batchArgs.questions[0]) },
    { questions: [batchArgs.questions[0], batchArgs.questions[0]] }, { questions: [{ ...batchArgs.questions[0], id: "bad id" }] },
    { questions: [{ ...batchArgs.questions[0], header: "A very long header" }] }]) assert.throws(() => validateBatch(invalid));
  const batchCall = (args) => tools.get("request_user_input").execute(args, { aborted: false }, { sessionId: "origin", messageId: 2, partId: 1 });
  const queuedBatch = JSON.parse(await batchCall(batchArgs));
  assert.equal(queuedBatch.status, "pending");
  assert.deepEqual(queuedBatch.questions.map((item) => item.id), ["features", "owner"]);
  assert.equal(JSON.parse(await batchCall(batchArgs)).id, queuedBatch.id);
  await assert.rejects(tools.get("request_user_input").execute(batchArgs, { aborted: true }, { sessionId: "origin", messageId: 2, partId: 2 }), /canceled/);
  const structured = { features: { answers: ["Logging", "Metrics", "user_note: Both"] }, owner: { answers: [] } };
  const batchMessage = batchAnswerMessage({ id: "batch", questions: normalized, answers: structured });
  assert.match(batchMessage, /Empty answer arrays.*NOT approval/);
  assert.match(batchMessage, /"features":\{"answers":\["Logging","Metrics","user_note: Both"\]\}/);
  async function checkStartupShortcut(sessionId, changed = "") {
    let release;
    execBarrier = new Promise((resolve) => { release = resolve; });
    const owned = [];
    const view = { name: "chat", session: { sessionId } };
    const root = { active: view, overlays: [], invalidate() {} };
    let opened = 0;
    let navigated = 0;
    let onEvent;
    const c = { alive: true, own: (fn) => owned.push(fn), on() {},
      advise: (target, name, kind, handler) => { if (target === root) onEvent = handler; },
      tui: { root, style: { set() {} }, status: { add() {} }, keymap: { add() {} },
        command: { add() {}, perform: () => opened++ } },
    };
    const scope = { alive: true, own: (fn) => owned.push(fn), hook() {},
      inject: (dependencies, apply) => { if (dependencies.includes("tui")) apply(c); },
      tools: { define() {} }, interaction: { notify: (...args) => notices.push(args) },
    };
    try {
      yukeClarify.apply(scope);
      onEvent(() => navigated++, { type: "key", code: "char", char: "h", mods: 4, event: "press" });
      assert.equal(opened + navigated, 0, "Ctrl+H must wait for the initial inbox snapshot");
      if (changed === "session") view.session.sessionId = "different-session";
      if (changed === "modal") root.overlays.push({ modal: true });
      release();
      await owned[1]();
      await new Promise((resolve) => setImmediate(resolve));
      assert.equal(opened, changed || sessionId !== "origin" ? 0 : 1);
      assert.equal(navigated, !changed && sessionId !== "origin" ? 1 : 0);
    } finally {
      release();
      c.alive = scope.alive = false;
      execBarrier = Promise.resolve();
      for (const dispose of owned) await dispose();
    }
  }
  await checkStartupShortcut("origin");
  await checkStartupShortcut("no-questions");
  await checkStartupShortcut("origin", "session");
  await checkStartupShortcut("origin", "modal");
  assert.equal(notices.length, 0);
  console.log("Clarification tool checks passed (real persistence; startup shortcut guards; no provider/network)");
} finally {
  for (const release of cleanup.reverse()) await release();
  delete globalThis.clarifyTest;
  await rm(root, { recursive: true, force: true });
}
