#!/usr/bin/env node
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

let forward = 0, executions = [], records = [], sudoCalls = [], notices = [], details = [], key, tool;
let outcome = { stdout: "command-marker\n", code: 0, signal: null, timedOut: false };
let pending, saveFails = false, resolutionFails = false, detailsFail = false, protocol = 2;
class Session {
  sessionId = "original-chat";
  creating = false;
  send() { forward++; return true; }
  async startChat() { return this.sessionId; }
}
let focused = new Session();
const ctx = {
  alive: true,
  signal: { aborted: false },
  tools: { define(value) { tool = value; } },
  use(plugin) {
    const signal = { aborted: false };
    plugin.apply({ ...ctx, signal });
    return { dispose() { signal.aborted = true; if (pending?.signal === signal) { pending.reject(new Error("canceled")); pending = null; } } };
  },
  inject(_caps, apply) { apply(c); },
};
const c = {
  alive: true,
  chat: { render() {} },
  interaction: { notify(...args) { notices.push(args); } },
  advise(object, name, _where, advice) { const original = object[name]; object[name] = function (...args) { return advice.call(this, original.bind(this), ...args); }; },
  tui: { keymap: { add(bindings) { key = bindings["ctrl+c"]; } } },
};
globalThis.composerTest = {
  Session, currentPane: () => ({ session: focused }),
  env: { get: name => name === "HOME" ? "/home/test" : undefined },
  lines() {}, spawn() { throw new Error("No privileged process belongs in this unit test."); },
  openDetails(...args) { details.push(args); if (detailsFail) throw new Error("details window failed"); },
  client: {
    async sessionGet() { return { session: { root: "/workspace" } }; },
    async request(method, params) { if (method === "initialize") return { protocol }; assert.equal(method, "session.record_command"); if (saveFails) throw new Error("save failed"); records.push(JSON.parse(JSON.stringify(params))); return { input_id: records.length }; },
  },
  async exec(command, options) {
    executions.push({ command, options });
    if (command.startsWith("python3 ")) return { code: resolutionFails ? 2 : 0, stdoutDropped: 0, stdout: '["/usr/bin/id","-u"]' };
    if (command === "sleep 100") return new Promise((resolve, reject) => { pending = { resolve, reject, signal: options.signal }; });
    return outcome;
  },
};
const source = (await readFile(new URL("../plugins/sudo-command.js", import.meta.url), "utf8"))
  .replace('import { client, env, exec, lines, spawn } from "yuke";', 'const { client, env, exec, lines, spawn } = globalThis.composerTest;')
  .replace('import { openDetails } from "yuke:chat";', 'const { openDetails } = globalThis.composerTest;')
  .replace('import { Session, currentPane } from "yuke:session";', 'const { Session, currentPane } = globalThis.composerTest;');
const { sudoCommand } = await import("data:text/javascript;base64," + Buffer.from(source).toString("base64"));
sudoCommand.apply(ctx);
tool.execute = async (args, signal, workspace) => { sudoCalls.push({ args, signal, workspace }); return { output: JSON.stringify({ stdout: "0\n", stderr: "", exit_code: 0, signal: null, timed_out: false }) }; };
const composer = { text: "", snapshot() { return { text: this.text }; }, restore(value) { this.text = value.text; } };
function submit(text, attachments = []) {
  composer.text = text;
  const accepted = focused.send([{ type: "text", text }, ...attachments], composer);
  if (accepted) composer.text = "";
  return accepted;
}
async function waitFor(predicate) {
  for (let i = 0; i < 100; i++) { await new Promise(resolve => setImmediate(resolve)); if (predicate()) { await new Promise(resolve => setImmediate(resolve)); return; } }
  throw new Error("The command did not settle.");
}
assert.equal(submit("normal prompt"), true);
assert.equal(submit("/context"), true);
assert.equal(forward, 2);
assert.equal(submit("!"), false);
assert.equal(submit("!pwd", [{ type: "image", source: {} }]), false);
assert.equal(composer.text, "!pwd");
assert.equal(executions.length, 0);
submit("!printf '$HOME' | cat");
await waitFor(() => records.length === 1);
assert.equal(forward, 2, "direct commands must not call Session.send or start a model reply");
assert.equal(records[0].output, "command-marker\n");
assert.equal(records[0].command.command, "printf '$HOME' | cat");
assert.equal(executions[0].command, "printf '$HOME' | cat");
assert.equal(executions[0].options.workspaceRoot, "/workspace");
assert.equal(executions[0].options.mergeStderr, true);
assert.equal(executions[0].options.log, false);
outcome = { ...outcome, code: 17 };
submit("!false");
await waitFor(() => records.length === 2);
assert.equal(records[1].command.exit_code, 17);
submit("!sudo id -u");
await waitFor(() => records.length === 3);
assert.deepEqual(sudoCalls[0].args.argv, ["/usr/bin/id", "-u"]);
assert.equal(sudoCalls[0].workspace.workspaceRoot, "/workspace");
assert.equal(records[2].output, "0\n");
resolutionFails = true;
submit("!sudo id | cat");
await waitFor(() => composer.text === "!sudo id | cat");
assert.equal(sudoCalls.length, 1);
resolutionFails = false;
submit("!sleep 100");
await waitFor(() => pending);
assert.equal(submit("!pwd"), false, "an active command must not consume a second command");
assert.equal(key(), true);
await waitFor(() => records.length === 4);
assert.match(records[3].output, /canceled.*may have started/i);
assert.equal(key(), false, "Ctrl+C must pass to normal bindings after cancellation");
submit("!sleep 100");
await waitFor(() => pending);
focused.sessionId = "different-chat";
pending.resolve(outcome);
pending = null;
await waitFor(() => records.length === 5);
assert.equal(records[4].session_id, "original-chat", "navigation must not move command output into another chat");
saveFails = true;
submit("!pwd");
await waitFor(() => details.length === 1);
assert.equal(composer.text, "", "a save failure must not offer to execute the command again");
assert.match(details[0][1][0].text, /command-marker/);
assert.ok(notices.some(([text]) => text.includes("Do not run it again")));
detailsFail = true;
const noticesBefore = notices.length;
submit("!pwd");
await waitFor(() => notices.length > noticesBefore);
assert.equal(composer.text, "", "an output-window failure must not restore an executed command");
assert.ok(notices.at(-1)[0].includes("may have run"));
const executionsBefore = executions.length;
protocol = 1;
sudoCommand.apply(ctx);
submit("!pwd");
await waitFor(() => composer.text === "!pwd");
assert.equal(executions.length, executionsBefore, "an old native API must fail before command execution");
assert.ok(notices.at(-1)[0].includes("Restart Yuke"));
assert.equal(forward, 2);
console.log("Composer command forwarding, sudo routing, cancellation, chat identity, and record-only sharing checks passed");
