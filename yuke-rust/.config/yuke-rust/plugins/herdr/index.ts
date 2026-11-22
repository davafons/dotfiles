import { connect } from "yuke:net";
import type { PluginContext } from "yuke:plugins";
import { env } from "yuke:process";
import { TextView } from "yuke:tui";
import type {} from "../../navigation.ts";
import { fileReferenceAt } from "./file-locations.js";

interface Reply {
  readonly type: string;
  readonly panes?: readonly {
    readonly pane_id: string;
    readonly agent?: string;
    readonly tokens?: Record<string, string>;
  }[];
}

async function request(method: string, params: unknown, signal: AbortSignal): Promise<Reply> {
  const path = env.get("HERDR_SOCKET_PATH");
  if (path === undefined) throw new Error("No Herdr socket is configured.");
  using socket = await connect({
    path,
    signal: AbortSignal.any([signal, AbortSignal.timeout(1000)]),
  });
  const id = `yuke:${method}`;
  await socket.write(new TextEncoder().encode(`${JSON.stringify({ id, method, params })}\n`));
  const reader = socket.readable.getReader();
  const decoder = new TextDecoder();
  let text = "";
  try {
    for (;;) {
      const chunk = await reader.read();
      if (chunk.done) throw new Error("Herdr closed an incomplete response.");
      text += decoder.decode(chunk.value, { stream: true });
      if (text.length > 1024 * 1024) throw new Error("Herdr response exceeds 1 MiB.");
      const newline = text.indexOf("\n");
      if (newline < 0) continue;
      const reply: unknown = JSON.parse(text.slice(0, newline));
      if (typeof reply !== "object" || reply === null || !("id" in reply) || reply.id !== id)
        throw new Error("Invalid Herdr response.");
      if ("error" in reply) throw new Error("Herdr refused the request.");
      if (
        !("result" in reply) ||
        typeof reply.result !== "object" ||
        reply.result === null ||
        !("type" in reply.result) ||
        typeof reply.result.type !== "string"
      )
        throw new Error("Herdr returned no result.");
      return reply.result as Reply;
    }
  } finally {
    reader.releaseLock();
  }
}

/** Connect file and session navigation and report this terminal's state to Herdr. Nested agents never report over a pane. */
export function apply(ctx: PluginContext): (() => Promise<void>) | undefined {
  const navigation = ctx.get("personal-navigation");
  const tui = ctx.get("tui");
  const inside = env.get("HERDR_ENV") === "1" && env.get("HERDR_SOCKET_PATH") !== undefined;
  if (inside) {
    const remove = navigation.installBridge({
      focusSession: async (id) => {
        const reply = await request("pane.list", {}, ctx.signal);
        if (reply.type !== "pane_list" || !Array.isArray(reply.panes)) throw new Error("Invalid Herdr pane list.");
        const pane = reply.panes.find((pane) => pane.agent === "yuke" && pane.tokens?.yuke_session_id === id);
        if (pane === undefined) return false;
        const focused = await request("pane.focus", { pane_id: pane.pane_id }, ctx.signal);
        if (focused.type !== "ok") throw new Error("Herdr did not focus the session owner.");
        return true;
      },
      openFile: async (url, cwd) => {
        const reply = await request(
          "plugin.action.invoke",
          {
            plugin_id: "david.code",
            action_id: "open-file",
            context: {
              invocation_source: "yuke",
              focused_pane_id: env.get("HERDR_PANE_ID"),
              focused_pane_cwd: cwd,
              clicked_url: url,
            },
          },
          ctx.signal,
        );
        if (reply.type !== "ok") throw new Error("Herdr Code did not accept the file reference.");
      },
    });
    ctx.signal.addEventListener("abort", remove, { once: true });
  }
  if (tui === undefined) return;
  tui.widgets.addWatcher((mount) => {
    const view = mount.widget;
    if (!(view instanceof TextView) || view.role !== "transcript") return;
    const extension = view.extend(mount.signal);
    extension.addMouseHandler((event) => {
      if (
        !inside ||
        event.button !== "left" ||
        event.action !== "press" ||
        event.modifiers.ctrl ||
        event.modifiers.alt ||
        event.modifiers.shift ||
        event.modifiers.super
      )
        return false;
      const position = view.hitTest(event);
      if (position === undefined) return false;
      const section = view.document.items
        .find((item) => item.id === position.item)
        ?.sections.find((section) => section.id === position.section);
      if (section === undefined) return false;
      const location = fileReferenceAt(section.text, position.offset);
      if (location === null) return false;
      void navigation
        .openFile(location.path, location.line, location.column)
        .catch((error: unknown) => ctx.notify("warn", `Code: ${String(error)}`));
      return true;
    });
    return () => extension.close();
  });
  if (!inside || env.get("AI_AGENT") !== undefined || env.get("CLAUDECODE") !== undefined) return;
  const pane = env.get("HERDR_PANE_ID");
  if (pane === undefined) return;
  let ready = false;
  let sequence = Date.now();
  let desired = "";
  let acknowledged = "";
  let acknowledgedSession: string | undefined;
  let active: Promise<void> | undefined;
  let attempts = 0;
  const states = new Map<string, { busy: boolean; failed: boolean; questions: Set<number>; summary: string }>();
  const refresh = (): void => {
    if (!ready || ctx.signal.aborted) return;
    const view = tui.panes.activePane?.view;
    const id = view === undefined ? undefined : ctx.get("chat").sessionIdOf(view);
    const state = id === undefined ? undefined : states.get(id);
    const pending = id === undefined ? false : ctx.get("yuke-clarify").pending(id);
    const status =
      pending || state?.failed || (state?.questions.size ?? 0) > 0 ? "blocked" : state?.busy ? "working" : "idle";
    const value = JSON.stringify({ id: id ?? "", status, summary: state?.summary ?? "" });
    if (value !== desired) {
      desired = value;
      attempts = 0;
    }
    if (active !== undefined || desired === acknowledged || attempts >= 3) return;
    attempts += 1;
    const snapshot = desired;
    active = (async () => {
      const params = (): Record<string, unknown> => {
        sequence = Math.max(sequence + 1, Date.now());
        return {
          pane_id: pane,
          source: "custom:yuke",
          agent: "yuke",
          seq: sequence,
        };
      };
      if (id === undefined && acknowledgedSession !== undefined)
        await request("pane.release_agent", params(), ctx.signal);
      await request(
        "pane.report_agent",
        {
          ...params(),
          state: status,
          ...(id === undefined ? {} : { agent_session_id: id, resume_argv: ["yuke", "--session", id] }),
        },
        ctx.signal,
      );
      await request(
        "pane.report_metadata",
        { ...params(), tokens: { summary: state?.summary ?? "", yuke_session_id: id ?? "" } },
        ctx.signal,
      );
      acknowledged = snapshot;
      acknowledgedSession = id;
    })()
      .catch((error: unknown) => {
        if (!ctx.signal.aborted && attempts >= 3) console.log("Herdr report failed", String(error));
      })
      .finally(() => {
        active = undefined;
        if (!ctx.signal.aborted && acknowledged !== desired) tui.addTimer(250, refresh);
      });
  };
  ctx.addListener("session.opened", (event) => {
    const state = {
      busy: event.state === "running",
      failed: false,
      questions: new Set<number>(event.interactions),
      summary: "",
    };
    states.set(event.sessionId, state);
    void ctx
      .get("sessions")
      .get(event.sessionId)
      .then(
        (row) => {
          state.summary = (row.title ?? "").slice(0, 72);
          refresh();
        },
        () => {},
      );
  });
  ctx.addListener("session.update", (event) => {
    const state = states.get(event.sessionId);
    if (state === undefined) return;
    const update = event.update;
    if (update.kind === "state") {
      state.busy = update.state === "running";
      if (state.busy) state.failed = false;
    } else if (update.kind === "commit") {
      if (update.commit.end?.kind === "failed") state.failed = true;
    } else if (update.kind === "inputAccepted" && update.input.source.kind === "user" && state.summary === "") {
      void ctx
        .get("sessions")
        .get(event.sessionId)
        .then(
          (row) => {
            state.summary = (row.title ?? "").slice(0, 72);
            refresh();
          },
          (error: unknown) => console.log("Herdr summary failed", String(error)),
        );
    } else if (update.kind === "interactionRequested") state.questions.add(update.interactionId);
    else if (update.kind === "interactionClosed") state.questions.delete(update.interactionId);
    else return;
    refresh();
  });
  ctx.get("chat").addChangeListener(refresh);
  const stopQuestions = ctx.get("yuke-clarify").onChange(refresh);
  ctx.signal.addEventListener("abort", stopQuestions, { once: true });
  tui.widgets.addWatcher(() => {
    if (!ready) {
      ready = true;
      tui.addTimer(0, refresh);
    }
    return undefined;
  });
  return async () => {
    ready = false;
    await active;
    const params = (): Record<string, unknown> => {
      sequence = Math.max(sequence + 1, Date.now());
      return {
        pane_id: pane,
        source: "custom:yuke",
        agent: "yuke",
        seq: sequence,
      };
    };
    try {
      await request(
        "pane.report_metadata",
        { ...params(), tokens: { summary: "", yuke_session_id: "" } },
        AbortSignal.timeout(1000),
      );
      await request("pane.release_agent", params(), AbortSignal.timeout(1000));
    } catch (error) {
      console.log("Herdr exit report failed", String(error));
    }
  };
}
