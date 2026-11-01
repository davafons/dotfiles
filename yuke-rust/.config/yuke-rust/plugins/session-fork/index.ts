import type { PluginContext, SessionContext, Sessions } from "yuke:plugins";

let sessions: Sessions;

/** Keep the native session service for tools in each frontend. */
export function apply(ctx: PluginContext): undefined {
  sessions = ctx.get("sessions");
}

/** Add an explicit conversation fork. The tool starts no model turn and opens no pane. */
export function session(s: SessionContext): undefined {
  s.tools.define({
    name: "fork_session",
    description:
      "Fork this conversation only when the user requests it. Copy history through a completed turn to an independent session. Omit workspace_path to keep the source workspace and prompt. A destination folder supplies its own instructions, skills, and MCP configuration. Queued inputs, active drafts, children, and jobs stay with the source. No pane or model turn starts. A cancelled call can still create a fork; inspect sessions before retrying.",
    concurrency: "serial",
    parameters: {
      type: "object",
      properties: {
        workspace_path: { type: "string", description: "Existing absolute destination folder." },
        through_event: {
          type: "integer",
          minimum: 1,
          description: "Event number of the end of a completed turn. Omit to use the newest completed turn.",
        },
      },
    },
    execute: async (args, context) => {
      context.signal.throwIfAborted();
      const id = await sessions.fork(context.sessionId, args.through_event, args.workspace_path);
      const row = await sessions.get(id);
      return JSON.stringify({
        session_id: id,
        source_session_id: context.sessionId,
        workspace_path: row.session.cwd,
        resume_command: `yuke --session ${id}`,
      });
    },
  });
}
