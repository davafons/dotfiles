#!/usr/bin/env node
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const secret = "mock-private-secret";
let approval = true, password = secret, interactive = true;
let starts = [], prompts = [], owned = [], pending, barrier;
let failStart = false, failedWrite = false, killCount = 0;
let retryLimit = 0, exhausted = false, dialogReplies, waitDialog, dismissDialog;
globalThis.sudoTest = {
  Session: class {}, currentPane: () => null, openDetails: () => {}, client: {}, exec: () => {},
  env: { get: name => ({ HOME: "/home/test", XDG_CONFIG_HOME: "/tmp/test-config" })[name] },
  lines: callback => { let rest = ""; return text => { rest += text; const lines = rest.split("\n"); rest = lines.pop(); for (const line of lines) callback(line); }; },
  spawn: (argv, options) => {
    starts.push({ argv, options });
    let deliver;
    let writes = 0;
    const exited = new Promise((resolve, reject) => { pending = { resolve, reject }; });
    if (failStart) pending.reject(new Error(secret));
    return {
      exited,
      onStdout: callback => { deliver = callback; },
      write: async text => {
        if (failedWrite) throw new Error(secret);
        const request = JSON.parse(text);
        writes++;
        if (writes === 1) {
          assert.equal(request.password, secret);
          assert.deepEqual(request.argv, ["/usr/bin/id", "-u"]);
        }
        assert.ok(text.endsWith("\n"));
        assert.ok(!JSON.stringify(starts).includes(secret));
        if (barrier) await barrier;
        if (writes <= retryLimit && request.password !== "") {
          deliver(JSON.stringify({ type: "password", attempt: writes + 1 }) + "\n");
          return;
        }
        deliver(JSON.stringify({ type: "result", result: { stdout: "0\n" + secret, stderr: "", exit_code: exhausted || request.password === "" ? 1 : 0, signal: null, timed_out: false, canceled: request.password === "" } }) + "\n");
        pending.resolve({ code: 0, signal: null });
      },
      closeStdin: () => {},
      kill: () => { killCount++; pending.resolve({ code: null, signal: 15 }); },
    };
  },
};
const source = (await readFile(new URL("../plugins/sudo-command.js", import.meta.url), "utf8"))
  .replace('import { client, env, exec, lines, spawn } from "yuke";', 'const { client, env, exec, lines, spawn } = globalThis.sudoTest;')
  .replace('import { openDetails } from "yuke:chat";', 'const { openDetails } = globalThis.sudoTest;')
  .replace('import { Session, currentPane } from "yuke:session";', 'const { Session, currentPane } = globalThis.sudoTest;');
const { sudoCommand } = await import("data:text/javascript;base64," + Buffer.from(source).toString("base64"));
let tool;
const ctx = {
  alive: true, inject: () => {},
  use: plugin => { plugin.apply({ interaction: ctx.interaction }); return { dispose: () => { if (dismissDialog) dismissDialog(undefined); } }; },
  effect: start => { const cleanup = start(); owned.push(cleanup); return cleanup; },
  tools: { define: definition => { tool = definition; } },
  interaction: {
    get interactive() { return interactive; },
    confirm: async (title, message) => { prompts.push({ title, message }); return approval; },
    input: async (title, placeholder, options) => { prompts.push({ title, placeholder, options }); assert.equal(options.secret, true); if (waitDialog && title.includes("Try again")) return new Promise(resolve => { dismissDialog = resolve; }); return dialogReplies?.length ? dialogReplies.shift() : password; },
  },
};
sudoCommand.apply(ctx);
const args = { argv: ["/usr/bin/id", "-u"], reason: "Check effective root identity." };
const call = (value = args, signal = { aborted: false }) => tool.execute(value, signal, { workspaceRoot: "/workspace" });
for (const invalid of [null, {}, { ...args, password: secret }, { ...args, argv: ["id"] }, { ...args, argv: ["/bin/echo", "bad\x1btext"] },
  { ...args, reason: "bad\x1btext" }, { ...args, cwd: "" }, { ...args, timeout_ms: 0 }]) await assert.rejects(call(invalid));
assert.equal(starts.length, 0);
interactive = false;
await assert.rejects(call(), /TUI/);
interactive = true;
await assert.rejects(call(args, { aborted: true }), /canceled/);
approval = false;
assert.match((await call()).output, /No command ran/);
assert.equal(starts.length, 0);
assert.equal(prompts.length, 1, "denial must not open a password dialog");
approval = true;
password = undefined;
assert.match((await call()).output, /No command ran/);
assert.equal(starts.length, 0);
password = secret;
let result = await call();
assert.equal(result.is_error, false);
assert.equal(JSON.parse(result.output).stdout, "0\n[REDACTED]");
assert.ok(!JSON.stringify(prompts).includes(secret));
assert.deepEqual(starts[0].argv, ["python3", "/tmp/test-config/yuke/plugins/sudo-command.py"]);
assert.equal(starts[0].options.workspaceRoot, "/workspace");
assert.match(prompts[0].message, /\/usr\/bin\/id/);
assert.match(prompts[0].message, /Check effective root identity/);

retryLimit = 2;
dialogReplies = [secret, "wrong-second-test-password", "correct-third-test-password"];
const beforeStarts = starts.length, beforePrompts = prompts.length;
result = await call();
assert.equal(result.is_error, false);
assert.equal(starts.length, beforeStarts + 1, "password retries must not restart the command");
assert.equal(prompts.length, beforePrompts + 4, "one approval and three masked password dialogs");
assert.match(prompts.at(-2).title, /attempt 2/);
assert.match(prompts.at(-1).title, /attempt 3/);
exhausted = true;
assert.equal((await call()).is_error, true, "exhausted attempts must return to the model");
exhausted = false;
dialogReplies = [secret, undefined];
assert.match((await call()).output, /canceled/);
waitDialog = true;
const waiting = call();
await new Promise(resolve => setTimeout(resolve, 10));
pending.resolve({ code: 1, signal: null });
await assert.rejects(waiting, /execution failed/);
waitDialog = false;
dismissDialog = undefined;
retryLimit = 0;
dialogReplies = undefined;

for (const phase of ["start", "write"]) {
  failStart = phase === "start";
  failedWrite = phase === "write";
  await assert.rejects(call(), error => !error.message.includes(secret) && /execution failed/.test(error.message));
}
failStart = failedWrite = false;
let release;
barrier = new Promise(resolve => { release = resolve; });
const signal = { aborted: false };
const running = call(args, signal);
await new Promise(resolve => setTimeout(resolve, 10));
await assert.rejects(call(), /Another sudo request/);
signal.aborted = true;
await new Promise(resolve => setTimeout(resolve, 80));
release();
result = await running;
assert.equal(result.is_error, true);
assert.match(result.output, /canceled/);
assert.ok(killCount > 0);
barrier = undefined;
assert.equal((await call()).is_error, false, "cancellation must release the busy guard");
for (const cleanup of owned) cleanup();
console.log("sudo_command approval, masking, argument isolation, error privacy, and cancellation checks passed");
