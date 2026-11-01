import type { PluginContext, SessionContext } from "yuke:plugins";
import { Command } from "yuke:process";
import type { ObjectSchema } from "yuke:tools";
import { install } from "./ui.ts";

let database: string;
const statuses = ["now", "later", "blocked", "review", "done"] as const;
const properties = {
  action: { type: "string", enum: ["list", "get", "task", "notes", "claim", "release", "message", "progress"] },
  id: { type: "string", description: "Task ID for get or task update. Omit to create a task." },
  version: {
    type: "integer",
    minimum: 0,
    description: "Version from the latest read or mutation receipt. Required for updates and progress.",
  },
  title: { type: "string" },
  status: { type: "string", enum: statuses },
  notes: {
    type: "string",
    description:
      "Markdown task notes. Use short paragraphs, headings and bullet points. Keep coordination history in task messages.",
  },
  body: {
    type: "string",
    description:
      "Markdown task message for action message. Requires id. Appends a session-attributed coordination message without replacing notes; does not notify or start another session.",
  },
  github_url: {
    type: "string",
    description:
      "Optional github.com issue or PR URL. Empty clears the link; omit to retain it on an update. Internal status never updates GitHub.",
  },
  offset: { type: "integer", minimum: 0, description: "Task page offset. Each list returns at most 10 tasks." },
  include_done: { type: "boolean", description: "Include completed tasks in list. Defaults to false." },
} as const;
const parameters = {
  type: "object",
  additionalProperties: false,
  properties,
  required: ["action"],
} as const satisfies ObjectSchema;

/** Select the persistent task database. */
export function apply(ctx: PluginContext): undefined {
  database = `${ctx.dataDir}/work.sqlite3`;
  const tui = ctx.get("tui");
  if (tui === undefined) return;
  install(
    ctx,
    tui,
    async <T>(value: unknown, cwd: string, signal: AbortSignal): Promise<T> =>
      JSON.parse(
        await helper(
          "project-work-store",
          [database, JSON.stringify({ api_version: 2, root: cwd, ...(value as object) })],
          cwd,
          signal,
        ),
      ) as T,
    async <T>(value: unknown, cwd: string, signal: AbortSignal): Promise<T> =>
      JSON.parse(
        await helper("project-work-github", [JSON.stringify({ root: cwd, ...(value as object) })], cwd, signal),
      ) as T,
  );
}

async function helper(name: string, args: readonly string[], folder: string, signal: AbortSignal): Promise<string> {
  const output = await new Command("python3", {
    args: [`${import.meta.dirname}/../../helpers/${name}.py`, ...args],
    cwd: folder,
    signal,
  }).output();
  signal.throwIfAborted();
  const decoder = new TextDecoder();
  if (!output.success)
    throw new Error(decoder.decode(output.stderr) || decoder.decode(output.stdout) || `${name} failed`);
  return decoder.decode(output.stdout).trim();
}

/** Register shared tasks and read-only GitHub tools. Storage and process errors fail the call. */
export function session(s: SessionContext): undefined {
  s.hook("prompt.build", (event) => ({
    sections: {
      ...event.sections,
      "project-work":
        "Use project_work list when starting substantial work or resuming a project. Tasks are shared across linked checkouts. Read list/get when starting or resuming, or after a version conflict. Reuse the id/version returned by successful reads or mutations. For routine progress, prefer progress with a short body and optional status; it preserves scope notes. Rewrite scope notes only when scope, decisions, or acceptance changes. Do not reread a task solely to obtain the version you just received. Assign yourself a task with claim before working on it. Saving a task as now also claims it when unowned. A task is assigned directly to one session. A session can have only one assigned task across all projects. Complete or release the current task before claiming another. Child agents use their own session assignments. The work UI can release a closed owner only when its native session lock and the Herdr inventory agree; idle, blocked and unknown presence retain claims. Never infer assignment from a creator chat or the now status. If another session is assigned to the task, post a message to coordinate or choose another task. Messages are read with get or UI refresh, not pushed to sessions. Release your claim when you stop working on the task; done releases it. Update notes in readable Markdown with short paragraphs and bullets. Use notes for notes-only edits; it preserves status and ownership. Keep task notes current with scope, decisions, and verification. Record failed and unrun checks. Do not mark a task done just because a run ended. The user reads /work. Reading records or preparing a brief does not authorize delegation, sending external messages, pushing, merging, or deployment. GitHub is the outer loop; read github_work for linked issues/PRs and keep internal task status separate. github_work is read-only.",
    },
  }));
  s.tools.define({
    name: "project_work",
    description:
      "Read and save shared project tasks across linked checkouts. list returns ten tasks. get requires id. task creates or updates title, status, and notes. Updates, claim, release, notes, and progress require a fresh version. claim assigns the task to this session. A session can hold one task. message appends coordination text. progress appends a message and optional status without replacing scope notes. done releases the assignment. Replaying a call returns its original receipt. No GitHub writes, notifications, or automatic completion.",
    concurrency: "serial",
    parameters,
    execute: (args, context) =>
      helper(
        "project-work-store",
        [
          database,
          JSON.stringify({
            ...args,
            api_version: 2,
            root: context.folder,
            session: context.sessionId,
            site: `${context.sessionId}:${context.callId}`,
          }),
        ],
        context.folder,
        context.signal,
      ),
  });
  s.tools.define({
    name: "github_work",
    description: "Read GitHub issues and pull requests for this checkout. This tool never writes to GitHub.",
    concurrency: "parallel",
    parameters: {
      type: "object",
      properties: {
        action: { type: "string", enum: ["list", "get"] },
        kind: { type: "string", enum: ["issues", "pulls"] },
        state: { type: "string", enum: ["open", "closed", "all"] },
        cursor: { type: "string" },
        url: { type: "string" },
      },
      required: ["action"],
    },
    execute: (args, context) =>
      helper(
        "project-work-github",
        [JSON.stringify({ ...args, root: context.folder })],
        context.folder,
        context.signal,
      ),
  });
}
