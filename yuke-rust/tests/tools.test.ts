import { mkdir, writeTextFile } from "yuke:fs";
import { assert, assertEquals, createHost, folder, reply, test, waitForSettled } from "yuke:test";
import {
  apply as agentApply,
  session as agentSession,
  savedRole,
} from "../.config/yuke-rust/plugins/agent-tools/src/index.ts";
import { session as skillSession } from "../.config/yuke-rust/plugins/dollar-skills/index.ts";
import { session as personalSession } from "../.config/yuke-rust/plugins/personal/index.ts";
import { apply as workApply, session as workSession } from "../.config/yuke-rust/plugins/project-work/index.ts";
import { session as sudoSession } from "../.config/yuke-rust/plugins/sudo-command/index.ts";
import { apply as clarifyApply, session as clarifySession } from "../.config/yuke-rust/plugins/yuke-clarify/index.ts";

const profile = `${import.meta.dirname}/../.config/yuke-rust/plugins`;

test("the personal prompt replaces the base and retains workspace instructions", async () => {
  await using host = await createHost({
    plugins: [{ name: "personal", session: personalSession }],
    replies: [reply.text("done")],
  });
  const session = await host.openSession();
  await session.sendMessage("Check the prompt.");
  const system = host.requests[0]?.system;
  assert(system !== undefined);
  assert(system.includes("Request several independent reads or searches in one response."));
  assert(system.includes("workspace:"));
});

test("project tasks retain scope through claimed progress and completion", async () => {
  await using host = await createHost({ plugins: [{ name: "project-work", apply: workApply, session: workSession }] });
  const session = await host.openSession();
  const created = await session.call("project_work", {
    action: "task",
    title: "Port plugins",
    status: "now",
    notes: "Keep scope.",
  });
  assert(!created.isError, created.text);
  const result = JSON.parse(created.text);
  const task = result;
  assert(typeof task.id === "string");
  const progress = await session.call("project_work", {
    action: "progress",
    id: task.id,
    version: task.version,
    body: "Verified tools.",
    status: "done",
  });
  assert(!progress.isError, progress.text);
  const read = await session.call("project_work", { action: "get", id: task.id });
  assert(!read.isError, read.text);
  const saved = JSON.parse(read.text).task;
  assertEquals([saved.notes, saved.status, saved.owner_session], ["Keep scope.", "done", ""]);
  const stale = await session.call("project_work", {
    action: "notes",
    id: task.id,
    version: task.version,
    notes: "stale",
  });
  assert(stale.isError, stale.text);
});

test("web tools reject invalid input before network access", async () => {
  await using host = await createHost({ plugins: [{ folder: `${profile}/web` }] });
  const session = await host.openSession();
  const search = await session.call("web_search", { query: " " });
  const fetch = await session.call("web_fetch", { url: "file:///private/test" });
  assert(search.isError && search.text.includes("query is required"), search.text);
  assert(fetch.isError && fetch.text.includes("HTTP or HTTPS"), fetch.text);
});

test("an inherited delegate gets its role prompt and returns a model receipt without nested delegation tools", async () => {
  await using host = await createHost({
    plugins: [{ name: "agent-tools", apply: agentApply, session: agentSession }],
    replies: [reply.text("Reviewed the fixture.")],
  });
  const parent = await host.openSession();
  const result = await parent.call("spawn_agent", {
    agent: "dav-agent",
    message: "Review this fixture.",
    background: false,
  });
  assert(!result.isError, result.text);
  assert(result.text.includes("Engine model receipt:"), result.text);
  assert(result.text.includes("Reviewed the fixture."), result.text);
  const request = host.requests[0];
  assert(request !== undefined);
  assert(request.system.includes("Read ~/.agents/skills/dav-mode/SKILL.md in full"), request.system);
  assert(
    !request.tools.includes("spawn_agent") && !request.tools.includes("send_agent_input"),
    JSON.stringify(request.tools),
  );
});

test("a child of an earlier process gets its saved role back, and an unknown role falls back", async () => {
  const roles = `${folder()}/roles`;
  await mkdir(roles, { recursive: true });
  await writeTextFile(`${roles}/child-a.json`, JSON.stringify("reviewer"));
  await writeTextFile(`${roles}/child-b.json`, JSON.stringify("retired-role"));
  assertEquals(await savedRole(roles, "child-a"), "reviewer");
  assertEquals(await savedRole(roles, "child-b"), undefined);
  assertEquals(await savedRole(roles, "child-c"), undefined);
});

test("two explicit skills reach the model while the visible prompt keeps its original text", async () => {
  const cwd = `${folder()}/workspace`;
  for (const name of ["migration-alpha", "migration-beta"]) {
    const directory = `${cwd}/.agents/skills/${name}`;
    await mkdir(directory, { recursive: true });
    await writeTextFile(
      `${directory}/SKILL.md`,
      `---\nname: ${name}\ndescription: A test skill.\n---\nInstructions for ${name}.\n`,
    );
  }
  await using host = await createHost({
    plugins: [{ name: "dollar-skills", session: skillSession }],
    replies: [reply.text("done")],
  });
  const session = await host.openSession({ folder: cwd });
  const input = "Use $migration-alpha and $migration-beta. Keep `$ignored` literal.";
  await session.sendMessage(input);
  const request = host.requests[0];
  assert(request !== undefined);
  const text = request.messages.map((message) => message.text).join("\n");
  assert(text.includes("Instructions for migration-alpha.") && text.includes("Instructions for migration-beta."), text);
  const entry = session.transcript.entries.find((item) => item.kind === "input");
  assert(entry?.kind === "input");
  assertEquals(entry.content, [{ kind: "userText", text: input }]);
});

test("clarification tools persist pending receipts without answering or starting a model request", async () => {
  await using host = await createHost({
    plugins: [{ name: "yuke-clarify", apply: clarifyApply, session: clarifySession, provides: ["yuke-clarify"] }],
  });
  const session = await host.openSession();
  const question = await session.call("ask_question", {
    title: "Migration",
    question: "Keep saved chats?",
    options: [{ label: "Fresh chats", recommended: true }, { label: "Import" }],
  });
  assert(!question.isError, question.text);
  assertEquals(JSON.parse(question.text).status, "pending");
  const batch = await session.call("request_user_input", {
    questions: [
      { id: "storage", header: "Storage", question: "Use a new store?", options: [{ label: "Yes" }, { label: "No" }] },
    ],
  });
  assert(!batch.isError, batch.text);
  assertEquals(JSON.parse(batch.text).status, "pending");
  assertEquals(host.requests.length, 0);
});

test("declining a sudo request never launches its executable", async () => {
  await using host = await createHost({
    plugins: [{ name: "sudo-command", session: sudoSession }],
    onQuestion: () => [{ id: "approve", values: ["Do not run"] }],
  });
  const session = await host.openSession();
  const result = await session.call("sudo_command", { argv: ["/usr/bin/false"], reason: "Exercise the decline path." });
  assert(result.isError && result.text.includes("No command ran"), result.text);
  assertEquals(host.requests.length, 0);
});

test("recorded direct work reaches the next prompt without starting a model turn", async () => {
  let native: import("yuke:plugins").Sessions | undefined;
  let admissions = 0;
  await using host = await createHost({
    plugins: [
      {
        name: "recorder",
        apply: (ctx) => {
          native = ctx.get("sessions");
        },
        session: (s) => {
          s.addHook("input.before", () => {
            admissions += 1;
            return undefined;
          });
        },
      },
    ],
    replies: [reply.text("Read the recorded output.")],
  });
  const source = await host.openSession();
  assert(native !== undefined);
  const controller = new AbortController();
  try {
    const handle = await native.open(source.id, { tail: 0, signal: controller.signal, onEvent: () => {} });
    await handle.record({ display: "!pwd\n/workspace", text: "Completed direct command: /workspace" });
    await handle.waitForIdle();
    assertEquals([host.requests.length, admissions], [0, 0]);
    await source.sendMessage("Use the earlier command output.");
    assertEquals(admissions, 1);
    assert(JSON.stringify(host.requests[0]?.messages).includes("Completed direct command: /workspace"));
    const entry = source.transcript.entries.find((entry) => entry.kind === "input");
    assert(entry?.kind === "input");
    assertEquals(entry.content, [{ kind: "userText", text: "!pwd\n/workspace" }]);
  } finally {
    controller.abort();
  }
});

test("a destination fork uses the target instructions and leaves the source prompt unchanged", async () => {
  let native: import("yuke:plugins").Sessions | undefined;
  const base = `${folder()}/fork-fixture`;
  await mkdir(`${base}/source`, { recursive: true });
  await mkdir(`${base}/target`, { recursive: true });
  await writeTextFile(`${base}/source/AGENTS.md`, "ALPHA_SOURCE_ONLY");
  await writeTextFile(`${base}/target/AGENTS.md`, "BETA_DESTINATION_ONLY");
  const fork = await import("../.config/yuke-rust/plugins/session-fork/index.ts");
  await using host = await createHost({
    plugins: [
      {
        name: "session-fork",
        apply: (ctx) => {
          native = ctx.get("sessions");
          return fork.apply(ctx);
        },
        session: fork.session,
      },
      { name: "personal", session: personalSession },
    ],
  });
  const source = await host.openSession({ folder: `${base}/source` });
  const result = await source.call("fork_session", { workspace_path: `${base}/target` });
  assert(!result.isError, result.text);
  assert(native !== undefined);
  const id: string = JSON.parse(result.text).session_id;
  const target = await native.inspect(id);
  const original = await native.inspect(source.id);
  const targetPrompt = JSON.stringify(target.prompt),
    originalPrompt = JSON.stringify(original.prompt);
  assert(
    targetPrompt.includes("BETA_DESTINATION_ONLY") && !targetPrompt.includes("ALPHA_SOURCE_ONLY"),
    "The fork kept source instructions.",
  );
  assert(
    originalPrompt.includes("ALPHA_SOURCE_ONLY") && !originalPrompt.includes("BETA_DESTINATION_ONLY"),
    "The source prompt changed.",
  );
  assertEquals(host.requests.length, 0);
});

test("a recurring tick reaches its owning session once and stops when requested", async () => {
  const loop = await import("../.config/yuke-rust/plugins/loop/index.ts");
  await using host = await createHost({
    plugins: [{ name: "loop", apply: loop.apply, session: loop.session }],
    replies: [reply.text("The scheduled fixture ran.")],
  });
  const session = await host.openSession();
  const armed = await session.call("loop", {
    action: "arm",
    seconds: 1,
    prompt: "Check the exit condition for the fixture.",
  });
  assert(!armed.isError, armed.text);
  const deadline = Date.now() + 3000;
  while (host.requests.length === 0 && Date.now() < deadline)
    await new Promise<void>((resolve) => setTimeout(resolve, 20));
  const stopped = await session.call("loop", { action: "stop" });
  assert(!stopped.isError, stopped.text);
  assertEquals(host.requests.length, 1);
  assert(JSON.stringify(host.requests[0]?.messages).includes("Check the exit condition for the fixture."));
});

test("round hooks filter offered tools without a request to an external provider", async () => {
  await using host = await createHost({
    plugins: [
      {
        name: "filter",
        session: (s) => {
          s.tools.add({
            name: "visible",
            description: "Visible fixture",
            concurrency: "parallel",
            inputSchema: { type: "object", properties: {} },
            execute: () => "ok",
          });
          s.tools.add({
            name: "hidden",
            description: "Hidden fixture",
            concurrency: "parallel",
            inputSchema: { type: "object", properties: {} },
            execute: () => "ok",
          });
          s.addHook("round.before", () => ({ tools: ["visible"] }));
        },
      },
    ],
    replies: [reply.text("done")],
  });
  const session = await host.openSession();
  await session.sendMessage("Inspect the tool list.");
  assertEquals(host.requests[0]?.tools, ["visible"]);
});

test("a canceled delegate reports cancellation instead of completion", async () => {
  let sessions: import("yuke:plugins").Sessions | undefined;
  const gate = Promise.withResolvers<void>();
  await using host = await createHost({
    plugins: [
      {
        name: "agent-tools",
        apply: async (ctx) => {
          sessions = ctx.get("sessions");
          await agentApply(ctx);
        },
        session: async (s) => {
          await agentSession(s);
          s.tools.add({
            name: "cancellation_gate",
            description: "Hold the fixture until cancellation",
            concurrency: "parallel",
            inputSchema: { type: "object", properties: {} },
            execute: async (_args, context) => {
              const aborted = new Promise<void>((resolve) =>
                context.signal.addEventListener("abort", () => resolve(), { once: true }),
              );
              await Promise.race([gate.promise, aborted]);
              return "released";
            },
          });
        },
      },
    ],
    replies: [
      reply.toolCalls([{ name: "cancellation_gate", args: {} }]),
      reply.text("Received the cancellation report."),
    ],
  });
  const parent = await host.openSession();
  assert(sessions !== undefined);
  const parentScope = new AbortController();
  await sessions.open(parent.id, { tail: 0, signal: parentScope.signal, onEvent: () => {} });
  try {
    await parent.call("spawn_agent", { agent: "dav-agent", message: "Wait at the fixture gate.", background: true });
    await waitForSettled();
    assert(sessions !== undefined);
    const children = (await sessions.list({ parent: parent.id })).sessions;
    assertEquals(children.length, 1);
    const id = children[0]?.sessionId;
    assert(id !== undefined);
    const controller = new AbortController();
    const child = await sessions.open(id, { tail: 0, signal: controller.signal, onEvent: () => {} });
    child.cancelTurn();
    await waitForSettled();
    controller.abort();
    for (let attempt = 0; attempt < 100 && host.requests.length < 2; attempt += 1)
      await new Promise<void>((resolve) => setTimeout(resolve, 5));
    const text = host.requests.at(-1)?.messages.at(-1)?.text ?? "";
    assert(text.includes(": cancelled.") && text.includes("before it finished"), text);
  } finally {
    gate.resolve();
    parentScope.abort();
  }
});
