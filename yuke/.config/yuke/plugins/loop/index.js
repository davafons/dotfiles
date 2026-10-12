//! Register session-owned recurring prompts in every frontend.
import { client } from "yuke";
import { currentPane } from "yuke:session";
import { ChatView } from "yuke:chat";
import { intervalSeconds, SessionLoops } from "./core.js";

/** Own recurring inputs until unload. No TUI skips only commands and status. Invalid tool arguments or native delivery failures throw. @param {import("yuke").Context} ctx */
export default function apply(ctx) {
  const tui = ctx.get("tui");
  /** @type {Map<string, string>} */
  const status = new Map();
  /** @type {(() => void) | null} */
  let releaseInput = null;
  /** @type {(() => void) | null} */
  let releaseRun = null;
  /** @type {(() => void) | null} */
  let releaseStatus = null;
  const loops = new SessionLoops({
    async read(session) {
      const item = await client.sessionGet(session);
      let draft = false;
      if (tui) {
        const leaves = tui.root.root_node?.leaves() || [];
        for (let i = 0; i < leaves.length; i++) {
          const shape = leaves[i]?.shape;
          if (shape?.type !== "leaf") continue;
          const pane = shape.view;
          if (pane instanceof ChatView && pane.session.sessionId === session && (pane.composer.text || pane.composer.hasImages())) { draft = true; break; }
        }
      }
      return { idle: item.activity.state.type === "idle" && !draft, queued: item.activity.queued };
    },
    send: (session, text) => client.sessionSendInput(session, client.textContent(text)),
    cancel: (session, input) => client.sessionCancelInput(session, input),
    changed(session) {
      if (!ctx.alive) return;
      const jobs = loops.list(session);
      if (jobs.length) status.set(session, `loop ${jobs.filter(job => job.state !== "paused").length}/${jobs.length}`);
      else status.delete(session);
      if (loops.jobs.size) {
        if (!releaseInput) releaseInput = ctx.hook("input.before", admit);
        if (!releaseRun) releaseRun = ctx.on("run.done", ended);
        if (tui && !releaseStatus) releaseStatus = tui.status.add({ side: "right", order: 65, render: () => {
          const current = currentPane()?.session.sessionId;
          return current ? status.get(current) || "" : "";
        } });
      } else {
        releaseInput?.(); releaseInput = null;
        releaseRun?.(); releaseRun = null;
        releaseStatus?.(); releaseStatus = null;
      }
      tui?.root.invalidate();
    },
  });
  let resets = Promise.resolve();
  ctx.own(() => Promise.all([loops.dispose(), resets]));
  /** @param {Extract<Parameters<import("yuke").HookHandler>[0], { content: readonly Wire.ContentPart[] }>} payload */
  function admit(payload) {
    if (payload.content[0]?.type !== "text" || !payload.content[0].text.startsWith("[yuke-loop ")) return;
    const text = payload.content.filter(part => part.type === "text").map(part => part.text).join("");
    if (!loops.admits(payload.session_id, text)) return { block: "This loop tick expired or was canceled. Rearm explicitly." };
  }
  /** @param {string} session */
  async function wake(session) {
    try {
      if (!ctx.alive) return;
      const outcome = client.sessionLastRun(session);
      await loops.wake(session, outcome?.type === "failed" || outcome?.type === "canceled" ? "A turn failed or was canceled. Stop this loop and rearm explicitly." : undefined);
    } catch (error) {
      if (ctx.alive) await loops.wake(session, "Cannot read the run outcome: " + String(error));
    }
  }
  /** @param {Parameters<import("yuke").Events["run.done"]>[0]} event */
  function ended(event) {
    if (!loops.jobs.size) return;
    if (event.type === "session") void wake(event.session);
    else {
      const ids = new Set(Array.from(loops.jobs.values(), job => job.session));
      ids.forEach(session => { void wake(session); });
    }
  }
  ctx.tools.define({
    name: "loop",
    description: "Arm, list, or stop recurring prompts in this session. Arm only after the operator explicitly requests scheduled turns. Include the exit condition in the prompt. The first tick waits one interval. Busy ticks coalesce. Stop cancels only future ticks and owned queued input, never an active run or unrelated input. Failed or canceled turns pause schedules. Quit and reload stop schedules without restoring them. This tool grants no delegation, write, push, merge, deploy, or desktop permission.",
    parameters: { type: "object", additionalProperties: false, properties: {
      action: { type: "string", enum: ["arm", "list", "stop"] },
      seconds: { type: "integer", minimum: 1, maximum: 2147483, description: "Required for arm." },
      prompt: { type: "string", minLength: 1, maxLength: 16000, description: "Required for arm. Include the exit condition and scope." },
      id: { type: "string", maxLength: 80, description: "For stop. Omit to stop all loops in this session." },
    }, required: ["action"] },
    async execute(raw, signal, toolCtx) {
      if (signal.aborted || !ctx.alive) throw Error("Loop request canceled.");
      if (!raw || typeof raw !== "object" || Array.isArray(raw)) throw Error("Loop arguments must be an object.");
      const args = /** @type {Record<string, unknown>} */ (raw);
      const allowed = args.action === "arm" ? ["action", "seconds", "prompt"] : args.action === "stop" ? ["action", "id"] : ["action"];
      if (Object.keys(args).some(name => !allowed.includes(name))) throw Error("Unexpected loop argument.");
      if (args.action === "list") return JSON.stringify(loops.list(toolCtx.sessionId));
      if (args.action === "stop") {
        if (Object.hasOwn(args, "id") && (typeof args.id !== "string" || !args.id)) throw Error("Loop id must be nonempty text.");
        return JSON.stringify(await loops.stop(toolCtx.sessionId, /** @type {string | undefined} */ (args.id)));
      }
      if (args.action !== "arm" || typeof args.seconds !== "number" || typeof args.prompt !== "string") throw Error("Arm requires seconds and prompt.");
      return JSON.stringify(loops.arm(toolCtx.sessionId, args.seconds, args.prompt));
    },
  });
  if (!tui) return;
  tui.command.add("loop", { desc: "schedule turns; /loop <5m> <prompt>, list, or stop [id]", slash: true, args: true,
    run(args) {
      const session = currentPane()?.session.sessionId;
      if (!session) { ctx.interaction.notify("Start a saved conversation before arming a loop.", "error"); return; }
      const text = String(args || "").trim();
      void (async () => {
        if (!text || text === "list") {
          const jobs = loops.list(session);
          ctx.interaction.notify(jobs.length ? jobs.map(job => `${job.id}: ${job.state}, every ${job.seconds}s. ${job.error || job.prompt}`).join("\n") : "No loops armed in this session.");
          return;
        }
        const [verb, ...parts] = text.split(/\s+/);
        if (verb === "stop") {
          if (parts.length > 1) throw Error("Use /loop stop or /loop stop <id>.");
          const result = await loops.stop(session, parts[0]);
          ctx.interaction.notify(`Stopped ${result.stopped.length} loop(s). An active turn continues.${result.notes.length ? "\n" + result.notes.join("\n") : ""}`);
          return;
        }
        if (!verb) throw Error("Use /loop <5m> <prompt>.");
        const job = loops.arm(session, intervalSeconds(verb), text.slice(verb.length).trim());
        ctx.interaction.notify(`Armed ${job.id}, every ${job.seconds}s while Yuke is open. The first tick waits one interval. Quit or reload stops it.`);
      })().catch(error => { if (ctx.alive) ctx.interaction.notify(String(error), "error"); });
    },
  });
  const contextCommand = tui.command.map["context:reload"];
  if (contextCommand) ctx.advise(contextCommand, "run", "before", () => { resets = Promise.all([resets, loops.clear()]).then(() => {}); });

}
