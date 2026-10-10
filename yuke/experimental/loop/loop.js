import { client } from "yuke";
import { currentPane } from "yuke:session";
import { intervalSeconds, SessionLoops } from "./loop-core.js";
/** @import { Plugin } from "yuke" */

export const loop = /** @type {Plugin} */ ({
  name: "session-loop",
  apply(ctx) {
    const loops = new SessionLoops({
      async read(session) {
        const item = await client.sessionGet(session);
        const pane = currentPane();
        const draft = pane?.session.sessionId === session && !!pane.composer?.input.text;
        return { idle: item.activity.state.type === "idle" && !draft, queued: item.activity.queued };
      },
      send: (session, text) => client.sessionSendInput(session, client.textContent(text)),
      cancel: (session, input) => client.sessionCancelInput(session, input),
    });
    let resets = Promise.resolve();
    ctx.own(() => Promise.all([loops.dispose(), resets]));
    ctx.hook("input.before", (payload) => {
      const text = payload.content.filter((part) => part.type === "text").map((part) => part.text).join("");
      if (!loops.admits(payload.session_id, text)) return { block: "This scheduled loop tick is canceled or expired. Arm a new loop explicitly." };
    });
    ctx.on("run.done", (event) => {
      if (event.type !== "session") return;
      void client.sessionGet(event.session).then((item) => {
        const outcome = item.last_run;
        return loops.wake(event.session, outcome && (outcome.type === "failed" || outcome.type === "canceled") ? "The runtime reported a failed or canceled turn. Stop this loop and rearm explicitly." : undefined);
      }).catch((error) => { if (ctx.alive) ctx.print("Loop wake failed:", String(error)); });
    });
    ctx.tools.define({
      name: "loop",
      description: "Arm, list, or stop recurring prompts in this session. Arm only when the operator explicitly authorized scheduled turns. State the exit condition in the prompt. The first tick waits one interval; busy ticks coalesce. Schedules stop on quit or profile reload and never restart automatically. Stop cancels future ticks and this loop's queued input, not an active turn or unrelated user input. Delivery errors pause the loop. A failed or canceled turn pauses it when the runtime reports that outcome. This tool grants no new delegation, write, push, merge, deploy, or desktop permission.",
      parameters: { type: "object", additionalProperties: false, properties: {
        action: { type: "string", enum: ["arm", "list", "stop"] },
        seconds: { type: "integer", minimum: 1, maximum: 2147483, description: "Required for arm." },
        prompt: { type: "string", minLength: 1, maxLength: 16000, description: "Required for arm. Include the goal, exit condition, and scope." },
        id: { type: "string", maxLength: 80, description: "For stop. Omit to stop all loops in this session." },
      }, required: ["action"] },
      async execute(args, signal, toolCtx) {
        if (signal.aborted || !ctx.alive) throw new Error("Loop request canceled.");
        if (!args || typeof args !== "object" || Array.isArray(args)) throw new Error("Loop arguments must be an object.");
        const value = /** @type {Record<string, unknown>} */ (args);
        const allowed = value.action === "arm" ? ["action", "seconds", "prompt"] : value.action === "stop" ? ["action", "id"] : ["action"];
        if (Object.keys(value).some((key) => !allowed.includes(key))) throw new Error("Unexpected field for this loop action.");
        const session = toolCtx.sessionId;
        if (value.action === "list") return JSON.stringify(loops.list(session));
        if (value.action === "stop") {
          if (value.id !== undefined && typeof value.id !== "string") throw new Error("Loop id must be a string.");
          return JSON.stringify(await loops.stop(session, value.id));
        }
        if (value.action !== "arm" || typeof value.seconds !== "number" || typeof value.prompt !== "string") throw new Error("Arm requires seconds and prompt; use list or stop for other actions.");
        return JSON.stringify(loops.arm(session, value.seconds, value.prompt));
      },
    });
    ctx.inject(["tui"], (c) => {
      c.tui.command.add("loop", {
        desc: "schedule turns; /loop <5m> <prompt>, list, or stop [id]",
        slash: true, args: true,
        run: (args) => {
          const session = currentPane()?.session.sessionId;
          if (!session) { c.interaction.notify("Start a saved conversation before arming a loop.", "error"); return; }
          const text = String(args || "").trim();
          void (async () => {
            if (!text || text === "list") {
              const jobs = loops.list(session);
              c.interaction.notify(jobs.length ? jobs.map((job) => `${job.id}: ${job.state}, every ${job.seconds}s. ${job.error || job.prompt}`).join("\n") : "No loops armed in this session.");
              return;
            }
            const [verb, ...parts] = text.split(/\s+/);
            if (verb === "stop") {
              if (parts.length > 1) throw new Error("Use /loop stop or /loop stop <id>.");
              const result = await loops.stop(session, parts[0]);
              c.interaction.notify(`Stopped ${result.stopped.length} loop(s). An active turn continues; Ctrl+C stops it.${result.notes.length ? "\n" + result.notes.join("\n") : ""}`);
              return;
            }
            const prompt = text.slice(verb.length).trim();
            const job = loops.arm(session, intervalSeconds(verb), prompt);
            c.interaction.notify(`Armed ${job.id}, every ${job.seconds}s while Yuke is open. The first tick waits one interval. Quit or reload stops it.`);
          })().catch((error) => { if (c.alive) c.interaction.notify(String(error), "error"); });
        },
      });
      c.advise(c.tui.command, "perform", "before", (name) => {
        if (name === "context:reload") {
          const clearing = loops.clear();
          resets = Promise.all([resets, clearing]).then(() => {});
        }
      });
      c.tui.status.add({ side: "right", order: 65, render: () => {
        const session = currentPane()?.session.sessionId;
        const jobs = session ? loops.list(session) : [];
        return jobs.length ? `loop ${jobs.filter((job) => job.state !== "paused").length}/${jobs.length}` : "";
      } });
    });
  },
});
