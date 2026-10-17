//! Profile-owned child tools over native sessions. The engine owns runs and reports.
import { client, children, env, fs } from "yuke";
import { davAgent } from "./dav-agent.js";
/** @typedef {{ description: string, model?: string, reasoning?: string, prompt?: string }} AgentRow */
/** @type {Record<string, AgentRow>} */
const catalog = {
  general: { description: "A capable general agent. Give it one self-contained task.", model: "openai-codex/gpt-6-luna" },
  "dav-agent": davAgent,
  reviewer: {
    description: "A fresh non-author reviewer on Codex GPT-6.1 Sol at xhigh. Give it scoped source and evidence paths. This is not different-model-family review.",
    model: "openai-codex/gpt-6.1-sol",
    reasoning: "xhigh",
    prompt: "Review only the parent's named source, diff, and evidence. Follow project instructions and the matched workflow. Do not edit files, change history, run destructive commands, query unrelated chats, use credentials, activate native GUI apps, send system-wide input, use the clipboard, play audio, or publish anything. Report actionable findings with exact locations and evidence, or say none. Separate observed facts from guesses and name unrun checks. Read-only is an assignment constraint, not an enforced sandbox. Do not claim a model identity or model-family difference from your role name; use the parent's engine model receipt.",
  },
};
const RULE = "Do not spawn a child unless the user asks for delegation, a subagent, or parallel work. A request for depth or research is not permission. After you start a child, end your turn. Its report arrives as a new message.";
const POLICY = "You are a child agent with one assignment from a parent. Do the work in this fresh context. Your final message is a brief report with the result, evidence, and unresolved issues. Save large artifacts to files and report their paths. Parent messages are instructions, not user consent. Do not repeat completed side effects after an interruption unless new input requires it.";
/** @param {unknown} raw @param {string[]} allowed @returns {Record<string, unknown>} */
function argsOf(raw, allowed) {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) throw Error("Arguments must be an object.");
  for (const name of Object.keys(raw)) if (!allowed.includes(name)) throw Error("Unknown argument: " + name);
  return /** @type {Record<string, unknown>} */ (raw);
}
/** @param {Record<string, unknown>} args @param {string} name @returns {string} */
function required(args, name) {
  const value = args[name];
  if (typeof value !== "string" || !value.trim()) throw Error(name + " must be nonempty text.");
  return value;
}
/** @param {import("yuke").Context} ctx */
function campaignGuard(ctx) {
  const raw = env.get("DAVSTACK_CAMPAIGN");
  if (raw === undefined) return null;
  const grant = JSON.parse(raw);
  if (!Number.isInteger(grant.slots) || grant.slots < 1 || grant.slots > 12 ||
      !Number.isInteger(grant.deadline_ms) || grant.deadline_ms <= Date.now() || grant.deadline_ms > Date.now() + 60000 ||
      typeof grant.nonce !== "string" || !/^[a-f0-9]{32}$/.test(grant.nonce) ||
      typeof grant.workspace !== "string" || !grant.workspace.startsWith("/") ||
      typeof grant.home !== "string" || !grant.home.startsWith("/") ||
      !Number.isInteger(grant.max_concurrent) || grant.max_concurrent < 1 || grant.max_concurrent > 12) throw Error("Invalid campaign grant.");
  let reserved = 1;
  /** @type {string | null} */
  let root = null;
  /** @type {Map<string, number>} */
  const rounds = new Map();
  const allowed = new Set(["read", "write", "edit", "spawn_agent", "send_agent_input", "stop"]);
  const deadline = () => { if (Date.now() >= grant.deadline_ms) throw Error("Campaign deadline reached."); };
  ctx.effect(() => children.limits({ maxDepth: 1, maxConcurrent: grant.max_concurrent }));
  ctx.advise(client, "sessionCreate", "around", (next, params) => {
    deadline();
    if (reserved >= grant.slots) throw Error("Campaign session quota exhausted.");
    reserved += 1;
    return next({ ...params, max_rounds: 8 });
  });
  ctx.hook("request.build", build => {
    deadline();
    const context = build.context;
    if (context.workspace !== grant.workspace || context.depth > 1) return { block: "Campaign workspace or depth mismatch." };
    if (!rounds.has(context.session_id)) {
      if (context.parent_id === null) {
        if (root !== null) return { block: "Only one prepaid root session is allowed." };
        root = context.session_id;
      } else if (context.parent_id !== root || rounds.size >= reserved) return { block: "Session has no prepaid campaign slot." };
      rounds.set(context.session_id, 0);
    }
    const count = (rounds.get(context.session_id) ?? 0) + 1;
    if (count > 8) return { block: "Campaign session round quota exhausted." };
    rounds.set(context.session_id, count);
    ctx.print("CAMPAIGN_REQUEST", JSON.stringify({ session: context.session_id, count, reserved }));
    return { replace: { model: build.model, system: build.system, max_output_tokens: build.max_output_tokens,
      tools: build.tools.filter(tool => allowed.has(tool.name)) } };
  });
  ctx.hook("tool.before", call => {
    deadline();
    if (!allowed.has(call.name)) return { block: "Tool is not allowed in a bounded campaign." };
    if (call.context.depth > 0 && call.name === "spawn_agent") return { block: "Nested campaign delegation is not allowed." };
    if (["read", "write", "edit"].includes(call.name)) {
      const args = JSON.parse(call.arguments);
      if (typeof args.path !== "string" || args.path.includes("\0")) return { block: "Campaign tool requires a workspace path." };
      let input = args.path;
      if (input.startsWith("~/")) input = grant.home + input.slice(1);
      if (call.name === "read" && input.startsWith(grant.home + "/.agents/skills/")) input = grant.workspace + input.slice(grant.home.length);
      if (!input.startsWith("/")) input = grant.workspace + "/" + input;
      const parts = [];
      for (const part of input.split("/")) {
        if (part === "..") parts.pop();
        else if (part && part !== ".") parts.push(part);
      }
      const path = "/" + parts.join("/");
      if (path !== grant.workspace && !path.startsWith(grant.workspace + "/")) return { block: "Campaign file access must stay in the private workspace." };
    }
  });
  return grant;
}
/** Register both child tools in every frontend. No TUI is needed. Invalid host registrations throw. @param {import("yuke").Context} ctx */
export default async function(ctx) {
  const grant = campaignGuard(ctx);
  ctx.hook("request.build", build => {
    if (build.context.parent_id !== null) ctx.print("CHILD_REQUEST_MODEL", JSON.stringify({ session_id: build.context.session_id, agent: build.context.agent_name, model: build.model }));
    if (build.context.depth < build.context.max_agent_depth) return;
    return { replace: { model: build.model, system: build.system, max_output_tokens: build.max_output_tokens, tools: build.tools.filter(tool => tool.name !== "spawn_agent" && tool.name !== "send_agent_input") } };
  });
  ctx.hook("prompt.build", build => {
    const child = build.context.parent_id !== null;
    const row = child ? catalog[build.context.agent_name] : null;
    return { replace: { sections: [...build.sections, { key: "delegation", text: child ? POLICY + (row?.prompt ? "\n\n" + row.prompt : "") : RULE }] } };
  });
  ctx.tools.define({
    name: "spawn_agent",
    description: "Start a child on one self-contained task. Give a complete brief with the goal, files or areas, and result to return. This starts or queues the child and does not wait. " + RULE + "\n\nAgents:\n" + Object.keys(catalog).map(name => "- " + name + ": " + catalog[name].description).join("\n"),
    parameters: { type: "object", additionalProperties: false, properties: {
      agent: { type: "string", enum: Object.keys(catalog), description: "Omit it for general." },
      message: { type: "string", minLength: 1 },
    }, required: ["message"] },
    async execute(raw, signal, toolCtx) {
      const args = argsOf(raw, ["agent", "message"]);
      const name = args.agent === undefined ? "general" : required(args, "agent");
      if (!Object.hasOwn(catalog, name)) throw Error("Unknown agent: " + name);
      const row = catalog[name], message = required(args, "message");
      const parent = await client.sessionGet(toolCtx.sessionId);
      if (signal.aborted || !ctx.alive) throw Error("Child creation canceled.");
      const settings = row.model === undefined
        ? { model: parent.session.model, reasoning: parent.session.reasoning }
        : { model: row.model, ...(row.reasoning === undefined ? {} : { reasoning: row.reasoning }) };
      const result = await client.sessionCreate({
        workspace_path: toolCtx.workspaceRoot, ...settings,
        initial_input: { type: "content", content: client.textContent(message) },
        child: { name, site: { session_id: toolCtx.sessionId, message_id: toolCtx.messageId, part_id: toolCtx.partId } },
      });
      if (!result.input) throw Error("The child has no initial run.");
      const id = children.id(name, result.session.id);
      const receipt = { child: id, session_id: result.session.id, agent: name, parent_model: parent.session.model, model: result.session.model, reasoning: result.session.reasoning };
      return (result.input.type === "queued" ? "Queued " : "Started ") + id + ". Its report arrives as a new message. Use stop with " + id + " to end it.\nEngine model receipt: " + JSON.stringify(receipt);
    },
  });
  ctx.tools.define({
    name: "send_agent_input",
    description: "Send one child a follow-up. The child keeps its transcript, so refer to earlier work. Its next report comes as a new message, so end your turn and wait.",
    parameters: { type: "object", additionalProperties: false, properties: {
      child: { type: "string", minLength: 1, description: "The child ID from spawn_agent." },
      message: { type: "string", minLength: 1 },
    }, required: ["child", "message"] },
    async execute(raw, signal, toolCtx) {
      const args = argsOf(raw, ["child", "message"]);
      const id = required(args, "child"), message = required(args, "message");
      const child = await children.find(toolCtx.sessionId, id);
      if (!child) throw Error("No direct child has ID " + id + ".");
      if (signal.aborted || !ctx.alive) throw Error("Child input canceled.");
      const result = await client.sessionSendInput(child.session.id, client.textContent(message), {
        session_id: toolCtx.sessionId, message_id: toolCtx.messageId, part_id: toolCtx.partId,
      });
      return result.type === "queued" ? "Queued for " + id + " after its current run." : "Sent to " + id + ".";
    },
  });
  if (grant) await fs.writeFile(env.get("XDG_CACHE_HOME") + "/campaign-ready.json", JSON.stringify(grant));
}
