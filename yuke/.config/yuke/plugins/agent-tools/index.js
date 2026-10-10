//! Profile-owned child tools over native sessions. The engine owns runs and reports.
import { client, children } from "yuke";
import { davAgent } from "./dav-agent.js";
/** @typedef {{ description: string, model?: string, reasoning?: string, prompt?: string }} AgentRow */
/** @type {Record<string, AgentRow>} */
const catalog = {
  general: { description: "A capable general agent. Give it one self-contained task.", model: "openai-codex/gpt-6-luna" },
  "dav-agent": davAgent,
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
/** Register both child tools in every frontend. No TUI is needed. Invalid host registrations throw. @param {import("yuke").Context} ctx */
export default function(ctx) {
  ctx.hook("request.build", build => {
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
      return (result.input.type === "queued" ? "Queued " : "Started ") + id + ". Its report arrives as a new message. Use stop with " + id + " to end it.";
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
}
