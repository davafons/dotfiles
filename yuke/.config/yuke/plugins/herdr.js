// Report this yuke pane as idle, working, or blocked to a local Herdr daemon.
// Herdr sets HERDR_ENV=1, HERDR_SOCKET_PATH, and HERDR_PANE_ID for the process.
import { client, env, net, plugins, utf8 } from "yuke";
import { currentEntry } from "yuke:session";
/** @import { Plugin } from "yuke" */

const source = "custom:yuke";
const agent = "yuke";
const timeoutMs = 250;
const frameLimit = 4096;
const maxAttempts = 3;

/**
 * Map Yuke's current chat state to one of the states accepted by Herdr.
 * A failed assistant message stays blocked until the user starts another run.
 * @param {number} pending
 * @param {boolean} busy
 * @param {ReturnType<typeof client.sessionOutline>} outline
 * @returns {"idle" | "working" | "blocked"}
 */
export function herdrAgentState(pending, busy, outline) {
  if (pending > 0) return "blocked";
  if (busy) return "working";
  const last = outline?.messages.at(-1);
  return last?.type === "assistant" && last.error ? "blocked" : "idle";
}

const summaryLimit = 72;

/**
 * Turn the text of a session's first user message into a stable sidebar summary.
 * @param {ReturnType<typeof client.sessionParts>} parts
 * @returns {string}
 */
export function herdrPromptSummary(parts) {
  let text = "";
  for (let index = 0; index < parts.length; index++) {
    const part = parts[index];
    if (part.type !== "text") continue;
    text += (text ? " " : "") + part.text;
  }
  const normalized = text.replace(/\s+/g, " ").trim();
  const chars = Array.from(normalized);
  if (chars.length <= summaryLimit) return normalized;
  const clipped = chars.slice(0, summaryLimit - 1);
  const boundary = clipped.lastIndexOf(" ");
  if (boundary >= Math.floor(summaryLimit / 2)) clipped.length = boundary;
  return clipped.join("") + "…";
}

/** @returns {Plugin} */
export function herdr() {
  return {
    name: "herdr",
    apply(ctx) {
      if (env.get("HERDR_ENV") !== "1") return;
      // A yuke that another agent starts inherits that agent's pane, so it must not report over that agent.
      if (env.get("AI_AGENT") || env.get("CLAUDECODE")) return;
      // `yuke check` builds the TUI composition without an interactive frontend. It inherits the
      // parent pane variables, so reporting there would steal and then release the live Yuke label.
      ctx.inject(["tui"], (ctx) => {
        if (!ctx.interaction.interactive) return;
        const path = env.get("HERDR_SOCKET_PATH");
        const pane = env.get("HERDR_PANE_ID");
        if (!path || !pane) return;
        const socketPath = path;
        let id = 0;
        // Herdr ignores a report whose seq is not above the last one it accepted, also across restarts, so seq follows the clock.
        let seq = 0;
        let attempts = 0;
        let retry = 0;
        let desiredState = "";
        let acknowledgedState = "";
        let desiredSummary = "";
        let acknowledgedSummary = "";
        // Reports are serialized, and cleanup waits for the active report, so one frame is sufficient.
        const frame = new Uint8Array(frameLimit);
        /** @type {Promise<void> | undefined} */
        let active;
        /** @type {Awaited<ReturnType<typeof net.connect>> | undefined} */
        let socket;

        /** @param {string} method @param {Record<string, unknown>} params @param {boolean} cleanup */
        async function request(method, params, cleanup) {
          const requestId = String(++id);
          seq = Math.max(seq + 1, Date.now());
          const bytes = utf8.encode(JSON.stringify({ id: requestId, method, params: { pane_id: pane, source, agent, seq, ...params } }) + "\n");
          if (bytes.length > frameLimit) throw new Error("Herdr request exceeds the byte limit");
          const options = cleanup ? { timeoutMs } : { timeoutMs, signal: ctx.signal };
          let expired = false;
          // One timer bounds the whole exchange, including partial response reads.
          const deadline = setTimeout(() => { expired = true; socket?.close(); }, timeoutMs);
          try {
            socket = await net.connect({ path: socketPath, ...options });
            if (expired || (!cleanup && !ctx.alive)) throw new Error("Herdr request canceled");
            await socket.write(bytes, options);
            let used = 0;
            let complete = false;
            while (!expired) {
              const chunk = await socket.read({ ...options, maxBytes: complete ? 1 : frameLimit + 1 });
              if (expired) throw new Error("Herdr request timed out");
              if (chunk === null) {
                if (complete) return;
                throw new Error("Incomplete Herdr response");
              }
              for (let at = 0; at < chunk.length; at++) {
                if (complete) throw new Error("Extra Herdr response data");
                const byte = chunk[at];
                if (byte === 10) {
                  const value = JSON.parse(utf8.decode(frame.subarray(0, used)));
                  if (!value || Array.isArray(value) || value.id !== requestId ||
                      "error" in value || value.result?.type !== "ok") throw new Error("Invalid Herdr response");
                  complete = true;
                  continue;
                }
                if (used === frameLimit) throw new Error("Herdr response exceeds the byte limit");
                frame[used++] = /** @type {number} */ (byte);
              }
            }
            throw new Error("Herdr request timed out");
          } finally {
            clearTimeout(deadline);
            socket?.close();
            socket = undefined;
          }
        }

        function schedule() {
          const settled = desiredState === acknowledgedState && desiredSummary === acknowledgedSummary;
          if (!ctx.alive || active || retry || settled || attempts === maxAttempts) return;
          const state = desiredState;
          const summary = desiredSummary;
          /** @type {unknown} */
          let failure;
          attempts++;
          active = (async () => {
            if (state !== acknowledgedState) {
              await request("pane.report_agent", { state }, false);
              acknowledgedState = state;
            }
            if (summary !== acknowledgedSummary) {
              await request("pane.report_metadata", { tokens: { summary } }, false);
              acknowledgedSummary = summary;
            }
          })().catch((error) => { failure = error; }).then(() => {
            active = undefined;
            const settled = desiredState === acknowledgedState && desiredSummary === acknowledgedSummary;
            if (!ctx.alive || settled) return;
            if (desiredState !== state || desiredSummary !== summary) schedule();
            else if (attempts < maxAttempts) retry = setTimeout(() => { retry = 0; schedule(); }, timeoutMs);
            else ctx.print("Herdr report failed", failure);
          });
        }

        function refresh() {
          const entry = currentEntry();
          const outline = entry ? client.sessionOutline(entry.session.id) : null;
          const state = herdrAgentState(ctx.interaction.pending, client.isBusy(), outline);
          const firstUser = outline?.messages.find((message) => message.type === "user");
          const summary = entry && firstUser ? herdrPromptSummary(client.sessionParts(entry.session.id, firstUser.id)) : "";
          if (state !== desiredState || summary !== desiredSummary) {
            desiredState = state;
            desiredSummary = summary;
            attempts = 0;
            clearTimeout(retry);
            retry = 0;
          }
          schedule();
        }

        // Disposal awaits this release; cleanup has its own deadline because the plugin signal is already canceled.
        ctx.own(async () => {
          clearTimeout(retry);
          socket?.close();
          await active;
          // Metadata tokens belong to their reporter, so clear the summary before releasing the agent label.
          try { await request("pane.report_metadata", { tokens: { summary: "" } }, true); } catch {}
          // Herdr documents release_agent as the exit report; it clears only the label that this source and agent hold.
          try { await request("pane.release_agent", {}, true); } catch {}
        });
        ctx.on("interaction.changed", refresh);
        ctx.on("engine.activity.changed", refresh);
        ctx.on("run.done", refresh);
        ctx.on("session.current.changed", refresh);
        ctx.on("session.summary_changed", refresh);
        refresh();
      });
    },
  };
}

