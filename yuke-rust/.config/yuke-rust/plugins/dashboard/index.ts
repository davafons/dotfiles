import type { PluginContext } from "yuke:plugins";
import { env } from "yuke:process";
import { strokeOf, TextEditor, TextView } from "yuke:tui";
import { command } from "../../lib.ts";
import { stdio } from "../../stdio.ts";
import { markdown } from "../../views.ts";
import { Dashboard } from "./view.ts";

const HOME = [
  { key: "l", label: "Sign in", command: "dashboard:login" },
  { key: "r", label: "Resume a session", command: "sessions-reworked:sessions" },
  { key: "s", label: "Search chats and files", command: "search:search" },
  { key: "w", label: "Project tasks and GitHub", command: "project-work:work" },
  { key: "m", label: "Choose a model", command: "models:model" },
  { key: "c", label: "Commands", command: "dashboard:commands" },
  { key: "q", label: "Quit Yuke", command: "core:quit" },
] as const;
/** Restore the centered dashboard in each empty, unsent normal-mode chat. Draft input stays in its composer. */
export function apply(ctx: PluginContext): undefined {
  const tui = ctx.get("tui");
  if (tui === undefined) return;
  const chat = ctx.get("chat"),
    vim = ctx.get("composer-vim");
  tui.styles.add({
    "dashboard.logo": { fg: "accent", bold: true },
    "dashboard.action": { fg: "strongFg" },
    "dashboard.key": { fg: "accent" },
    "dashboard.context": { inherits: "chat.meta" },
  });
  // The chat shows the model of the focused pane, also of an unsent draft, in its status item.
  const modelText = (): string | undefined => tui.status.list().find((item) => item.id === "chat:model")?.text;
  const stop = chat.setEmptyView((_mount, pane) => {
    const home = env.get("HOME");
    let folder = (chat.folder(pane.view) ?? tui.startup.cwd).replace(/[\x00-\x1f\x7f-\x9f]/gu, " ");
    if (home !== undefined && folder.startsWith(`${home}/`)) folder = `~${folder.slice(home.length)}`;
    const dashboard = new Dashboard(HOME, folder, (name) => {
      tui.focus(pane.composer);
      tui.commands.run(name);
    });
    let previous: string | undefined;
    let shown = false;
    return {
      draw: (canvas) => {
        if (vim?.mode(pane.composer) !== "normal") return;
        const pick = modelText();
        if (!shown || pick !== previous) {
          shown = true;
          previous = pick;
          dashboard.model(pick ?? "no model yet");
        }
        dashboard.draw(canvas);
      },
      onMouse: (event) => vim?.mode(pane.composer) === "normal" && dashboard.onMouse(event),
    };
  });
  ctx.signal.addEventListener("abort", stop, { once: true });
  command(ctx, tui, "commands", "Choose a command", async () => {
    const selected = await tui.select({
      title: "Commands",
      items: tui.commands.list().filter((row) => row.enabled),
      label: (row) => `${row.name} · ${row.description ?? ""}`,
      signal: ctx.signal,
    });
    if (selected !== undefined) tui.commands.run(selected.name);
  });
  command(ctx, tui, "login", "Sign in to a provider", async () => {
    const selected = await tui.select({
      title: "Sign in",
      items: (await ctx.get("catalog").list({ all: true })).providers,
      label: (row) => `${row.name} · ${row.state.kind}`,
      signal: ctx.signal,
    });
    if (selected === undefined) return;
    let output = "Starting sign-in…";
    const view = new TextView({ document: markdown("login", output) });
    const dialog = tui.dialog({
      title: () => `Sign in · ${selected.name} · Esc cancels`,
      body: view,
      rows: 12,
      signal: ctx.signal,
    });
    try {
      await stdio(
        [env.get("YUKE_EXECUTABLE") ?? "yuke", "login", selected.id],
        tui.startup.cwd,
        dialog.signal,
        async (connection) => {
          output = "";
          for (;;) {
            const event = await connection.read();
            if ("code" in event) {
              output += event.code === 0 ? "\nSign-in saved." : `\nSign-in failed (exit ${event.code}).`;
              break;
            }
            output = (output + event.text).slice(-8192);
            view.setDocument(markdown("login", output));
            tui.requestFrame();
          }
          view.setDocument(markdown("login", output));
          tui.requestFrame();
        },
      );
    } catch (error) {
      if (!dialog.signal.aborted) throw error;
    }
  });
  tui.widgets.addWatcher((mount) => {
    const editor = mount.widget;
    if (!(editor instanceof TextEditor) || editor.role !== "composer") return;
    const fresh = (): boolean =>
      mount.pane !== undefined &&
      editor.state.text === "" &&
      editor.state.spans.length === 0 &&
      chat.session(mount.pane.view) === undefined;
    if (fresh()) vim?.setMode(editor, "normal");
    const extension = editor.extend(mount.signal);
    extension.addKeyHandler((event) => {
      if (!fresh() || vim?.mode(editor) !== "normal" || vim.pending(editor)) return false;
      const key = strokeOf(event);
      const row = HOME.find((row) => row.key === key);
      if (row !== undefined) return tui.commands.run(row.command);
      if (
        !event.modifiers.ctrl &&
        !event.modifiers.alt &&
        !event.modifiers.super &&
        event.text !== "" &&
        event.text !== undefined &&
        key !== "i"
      ) {
        vim.setMode(editor, "insert");
        editor.replace(0, 0, event.text);
        return true;
      }
      return false;
    }, "beforeKeymap");
    return () => extension.dispose();
  });
}
