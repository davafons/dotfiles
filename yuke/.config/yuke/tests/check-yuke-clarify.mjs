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
try {
  const config = path.join(root, "config", "yuke", "plugins");
  await mkdir(config, { recursive: true });
  await copyFile(new URL("../plugins/yuke-clarify-store.py", import.meta.url), path.join(config, "yuke-clarify-store.py"));
  const variables = { HOME: root, XDG_CONFIG_HOME: path.join(root, "config"), XDG_STATE_HOME: path.join(root, "state") };
  globalThis.clarifyTest = {
    client: {}, events: {}, env: { get: (name) => variables[name] },
    exec: async (command) => {
      try { return { ...await promisify(shell)(command), code: 0 }; }
      catch (error) { return { stdout: error.stdout, stderr: error.stderr, code: error.code }; }
    },
  };
  let source = await readFile(new URL("../plugins/yuke-clarify.js", import.meta.url), "utf8");
  source = source.replace('import { client, env, events, exec } from "yuke";', 'const { client, env, events, exec } = globalThis.clarifyTest;')
    .replace('import { currentSession } from "yuke:session";', 'const currentSession = () => null;')
    .replace('import { clip, Composer, List, Pager, Window } from "yuke:ui";', 'const clip = (s) => s, Composer = class {}, List = class {}, Pager = class {}, Window = class {};')
    .replace('import { wrapRows } from "yuke:chat";', 'const wrapRows = () => [];');
  const { yukeClarify, validateQuestion, answerMessage } = await import("data:text/javascript;base64," + Buffer.from(source).toString("base64"));
  const ctx = { alive: true, own: (fn) => cleanup.push(fn), hook: (name, fn) => hooks.set(name, fn),
    inject: () => {}, tools: { define: (tool) => tools.set(tool.name, tool) },
    interaction: { notify: (...args) => notices.push(args) } };
  yukeClarify.apply(ctx);
  assert.equal(yukeClarify.name, "yuke-clarify");
  assert.deepEqual([...tools.keys()], ["ask_question"]);
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
  assert.equal(notices.length, 0);
  console.log("Clarification tool checks passed (real persistence; no provider/network)");
} finally {
  for (const release of cleanup.reverse()) await release();
  delete globalThis.clarifyTest;
  await rm(root, { recursive: true, force: true });
}
