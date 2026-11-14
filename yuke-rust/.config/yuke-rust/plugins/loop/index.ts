import type { ChatService } from "yuke:chat";
import type { PluginContext, SessionContext, SessionHandle, Sessions } from "yuke:plugins";
import { Transcript } from "yuke:transcript";
import { TextEditor, type Tui } from "yuke:tui";
import { command, currentSession } from "../../lib.ts";
import { intervalSeconds, SessionLoops } from "./core.js";

let sessions: Sessions;
let tui: Tui | undefined;
let chat: ChatService;
const managers = new Map<string, SessionLoops>();

/** Register loop commands. Loops run only while their owning session stays open. */
export function apply(ctx: PluginContext): undefined {
  sessions = ctx.get("sessions");
  tui = ctx.get("tui");
  chat = ctx.get("chat");
  const surface = tui;
  if (surface === undefined) return;
  command(
    ctx,
    surface,
    "loop",
    "Schedule /loop 5m prompt, list, or stop [id]",
    async (argument) => {
      const id = currentSession(ctx, surface);
      if (id === undefined) throw new Error("Start a saved conversation before arming a loop.");
      const loops = managers.get(id);
      if (loops === undefined) throw new Error("The loop session is not ready.");
      const parts = argument.trim().split(/\s+/);
      const verb = parts[0] ?? "";
      if (verb === "" || verb === "list") ctx.notify("info", JSON.stringify(loops.list(id)));
      else if (verb === "stop") ctx.notify("info", JSON.stringify(await loops.stop(id, parts[1])));
      else
        ctx.notify(
          "info",
          JSON.stringify(loops.arm(id, intervalSeconds(verb), argument.trim().slice(verb.length).trim())),
        );
    },
    "<interval prompt|list|stop [id]>",
  );
}

/** Add bounded recurring-input tools. A close, cancellation, failure, or reload stops their timers. */
export function session(s: SessionContext): () => Promise<void> {
  const transcript = new Transcript();
  let _handle: SessionHandle | undefined;
  let opening: Promise<SessionHandle> | undefined;
  const open = (): Promise<SessionHandle> => {
    opening ??= sessions
      .open(s.sessionId, {
        tail: 0,
        signal: s.signal,
        onEvent: (event) => {
          transcript.apply(event);
          if (event.kind !== "update") return;
          const update = event.update;
          if (update.sessionUpdate === "inputRemoved") loops.canceled(s.sessionId, update.inputId);
          if (update.sessionUpdate === "commit" && update.commit.end !== undefined) {
            const end = update.commit.end;
            const reason =
              end.kind === "failed"
                ? end.error
                : end.kind === "cancelled"
                  ? "The turn was cancelled. Rearm explicitly."
                  : undefined;
            void loops.wake(s.sessionId, reason).catch((error: unknown) => s.notify("error", String(error)));
          }
        },
      })
      .then((value) => {
        _handle = value;
        return value;
      });
    return opening;
  };
  const loops = new SessionLoops({
    read: async () => {
      await open();
      let draft = false;
      const surface = tui;
      if (surface !== undefined) {
        for (const mount of surface.widgets.list()) {
          if (
            mount.widget instanceof TextEditor &&
            mount.widget.role === "composer" &&
            mount.widget.state.text !== "" &&
            mount.pane !== undefined &&
            chat.session(mount.pane.view) === s.sessionId
          ) {
            draft = true;
            break;
          }
        }
      }
      return { idle: transcript.state === "idle" && !draft, queued: transcript.pending.size };
    },
    send: async (_id, text) => ({
      type: "queued",
      input_id: await (await open()).notifyModel({ display: "Recurring prompt", text }),
    }),
    cancel: async (_id, input) => (await open()).removeInput(input),
    changed: () => {
      tui?.requestFrame();
    },
  });
  managers.set(s.sessionId, loops);
  s.addHook("input.before", (event) => {
    const block = event.blocks[0];
    if (
      event.source.kind !== "plugin" ||
      event.source.name !== "loop" ||
      block === undefined ||
      !("kind" in block) ||
      block.kind !== "userText"
    )
      return undefined;
    const prefix = '<system_notification plugin="loop">';
    const suffix = "</system_notification>";
    const text =
      block.text.startsWith(prefix) && block.text.endsWith(suffix)
        ? block.text.slice(prefix.length, -suffix.length)
        : block.text;
    if (text.startsWith("[yuke-loop ") && !loops.admits(s.sessionId, text)) return { handled: true };
    return undefined;
  });
  s.tools.add({
    name: "loop",
    description:
      "Arm a recurring prompt only when the user requests recurrence. It waits until the session is idle and no user input waits. A cancel, failure, reload, or quit stops it. action list returns loops. stop ends one loop or all loops of this session; an active turn continues.",
    concurrency: "serial",
    inputSchema: {
      type: "object",
      properties: {
        action: { type: "string", enum: ["arm", "list", "stop"] },
        seconds: { type: "integer", minimum: 1, maximum: 2_147_483 },
        prompt: { type: "string" },
        id: { type: "string" },
      },
      required: ["action"],
    },
    execute: async (args) => {
      if (args.action === "list") return JSON.stringify(loops.list(s.sessionId));
      if (args.action === "stop") return JSON.stringify(await loops.stop(s.sessionId, args.id));
      if (args.seconds === undefined || args.prompt === undefined) throw new Error("Arm requires seconds and prompt.");
      await open();
      return JSON.stringify(loops.arm(s.sessionId, args.seconds, args.prompt));
    },
  });
  return async () => {
    managers.delete(s.sessionId);
    await loops.dispose();
    _handle = undefined;
  };
}
