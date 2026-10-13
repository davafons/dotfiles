//! Expose native conversation forks without starting another run or frontend.
import { client } from "yuke";

/** Register fork_session in every frontend. The plugin owns the registration. Invalid arguments, cancellation before admission, or native fork failures throw. @param {import("yuke").Context} ctx */
export default function(ctx) {
  ctx.tools.define({
    name: "fork_session",
    description: "Fork this conversation only when the user requests it. Copy committed history into an independent session. Omit workspace_path to keep this workspace. The live assistant draft, this call's result, queued input, children, and jobs do not transfer. Return the new session ID and resume command; do not open a pane or start a model turn. Launch the returned ID once through Herdr. A canceled call may still create a fork; inspect sessions before retrying.",
    parameters: {
      type: "object", additionalProperties: false,
      properties: {
        workspace_path: { type: "string", minLength: 1, description: "Existing absolute destination checkout directory." },
        before_message_id: { type: "integer", minimum: 1, maximum: Number.MAX_SAFE_INTEGER, description: "Exclusive committed-history boundary. Omit it to copy all committed messages." },
      },
    },
    async execute(raw, signal, toolCtx) {
      if (!raw || typeof raw !== "object" || Array.isArray(raw)) throw Error("Arguments must be an object.");
      const args = /** @type {{ workspace_path?: unknown, before_message_id?: unknown }} */ (raw);
      for (const key of Object.keys(args)) if (key !== "workspace_path" && key !== "before_message_id") throw Error("Unknown argument: " + key);
      const root = args.workspace_path;
      if (root !== undefined && (typeof root !== "string" || !root.trim())) throw Error("workspace_path must be nonempty text.");
      const before = args.before_message_id;
      if (before !== undefined && (typeof before !== "number" || !Number.isSafeInteger(before) || before < 1)) throw Error("before_message_id must be a positive safe integer.");
      if (signal.aborted || !ctx.alive) throw Error("Conversation fork canceled before admission.");
      const fork = await client.request("session.fork", {
        session_id: toolCtx.sessionId,
        ...(typeof root === "string" ? { workspace_path: root } : {}),
        ...(typeof before === "number" ? { before_message_id: before } : {}),
      });
      return JSON.stringify({ session_id: fork.id, source_session_id: toolCtx.sessionId, workspace_path: fork.root, message_count: fork.message_count, resume_command: "yuke resume " + fork.id });
    },
  });
}
