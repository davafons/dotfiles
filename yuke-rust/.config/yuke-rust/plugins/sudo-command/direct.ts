import type { PluginContext } from "yuke:plugins";
import { Command } from "yuke:process";
import { strokeOf, TextEditor, TextView, type Tui } from "yuke:tui";
import { EMPTY } from "../../lib.ts";
import { stdio } from "../../stdio.ts";
import { markdown } from "../../views.ts";
import { run } from "./index.ts";

/** Execute direct composer commands once, then record their receipt without an assistant reply. */
export function install(ctx: PluginContext, tui: Tui): void {
  const chat = ctx.get("chat"),
    vim = ctx.get("composer-vim");
  tui.widgets.addWatcher((mount) => {
    const editor = mount.widget;
    if (!(editor instanceof TextEditor) || editor.role !== "composer") return;
    const extension = editor.extend(mount.signal);
    let running = false;
    const execute = async (): Promise<void> => {
      const draft = editor.state;
      const source = draft.text.slice(1).trim();
      if (source === "" || mount.pane === undefined) return;
      running = true;
      const release = new AbortController();
      try {
        const id = await chat.ensureSession();
        if (id === undefined || editor.state !== draft || mount.signal.aborted) return;
        const cwd = chat.folder(mount.pane.view);
        if (cwd === undefined) throw new Error("The command has no working directory.");
        const handle = await ctx
          .get("sessions")
          .open(id, { tail: 0, signal: AbortSignal.any([ctx.signal, release.signal]), onEvent: () => {} });
        editor.reset(EMPTY);
        let output = "",
          status = "Running…",
          attempted = false,
          code: number | null = null;
        const controller = new AbortController();
        const view = new TextView({ document: markdown("command", `# !${source}\nRunning…`) });
        const dialog = tui.dialog({
          title: () => `Direct command · ${status}`,
          body: view,
          rows: Math.max(8, tui.size.height - 2),
          signal: ctx.signal,
          keys: [
            { key: "ctrl+c", label: "stop command", run: () => controller.abort() },
            { key: "pageup", label: "scroll up", run: () => view.scroll.scrollBy(-10) },
            { key: "pagedown", label: "scroll down", run: () => view.scroll.scrollBy(10) },
          ],
        });
        const signal = AbortSignal.any([controller.signal, dialog.signal]);
        const paint = (): void => {
          view.setDocument(markdown("command", `# !${source}\n\n${output}\n\n${status}`));
          tui.requestFrame();
        };
        try {
          if (/^sudo(?:\s|$)/u.test(source)) {
            const resolved = await new Command("python3", {
              args: [`${import.meta.dirname}/../../helpers/sudo-command.py`, "--resolve", source.slice(4).trim()],
              cwd,
              signal,
            }).output();
            if (!resolved.success) throw new Error(new TextDecoder().decode(resolved.stderr));
            const argv = JSON.parse(new TextDecoder().decode(resolved.stdout)) as string[];
            const approved = await tui.select({
              title: `Run as root in ${cwd}? ${JSON.stringify(argv)}`,
              items: [{ label: "Do not run" }, { label: "Run as root" }],
              label: (row) => row.label,
              signal,
            });
            if (approved?.label !== "Run as root") {
              status = "Declined. No command ran.";
              paint();
              return;
            }
            const result = await run(
              argv,
              cwd,
              120_000,
              signal,
              (attempt) =>
                new Promise<string | undefined>((resolve) => {
                  const field = new TextEditor({
                    mask: true,
                    multiline: false,
                    placeholder: "Sudo password · local only",
                  });
                  let answered = false;
                  const prompt = tui.dialog({
                    title: () => `Sudo password${attempt === 1 ? "" : ` · retry ${attempt}`}`,
                    body: field,
                    rows: 3,
                    signal,
                    keys: [
                      {
                        key: "enter",
                        label: "continue",
                        run: () => {
                          const value = field.state.text;
                          attempted = value !== "";
                          field.reset(EMPTY);
                          answered = true;
                          resolve(value);
                          prompt.close();
                        },
                      },
                    ],
                  });
                  prompt.signal.addEventListener(
                    "abort",
                    () => {
                      field.reset(EMPTY);
                      if (!answered) resolve(undefined);
                    },
                    { once: true },
                  );
                  tui.focus(field);
                }),
            );
            attempted = true;
            code = result.exit_code;
            output = [result.stdout, result.stderr].filter(Boolean).join("\n");
            status = result.canceled
              ? "Canceled"
              : result.timed_out
                ? "Timed out"
                : `Exit ${result.exit_code ?? result.signal}`;
          } else {
            await stdio(["/bin/sh", "-c", source], cwd, signal, async (connection) => {
              attempted = true;
              for (;;) {
                const event = await connection.read();
                if ("code" in event) {
                  code = event.code;
                  status = `Exit ${event.code}`;
                  break;
                }
                output = (output + event.text).slice(-48_000);
                paint();
                view.scroll.followTail();
              }
            });
          }
        } catch (error) {
          status = signal.aborted ? "Canceled · command output may be incomplete" : String(error);
        }
        paint();
        if (!attempted) {
          if (editor.state.text === "") editor.restore(draft);
          return;
        }
        const receipt = `Direct user command. This is a completed local action, not a request for an assistant reply.\nDirectory: ${cwd}\nCommand: ${source}\nStatus: ${status}\nExit code: ${code}\n\nOutput (last 48000 characters):\n${output}`;
        try {
          await handle.record({ display: `!${source}\n${status}\n\n${output}`, text: receipt });
        } catch (error) {
          status = `The command attempt ended. Saving its receipt failed. Do not rerun it to repair this save. ${String(error)}`;
          paint();
          throw error;
        }
      } finally {
        release.abort();
        running = false;
      }
    };
    extension.addKeyHandler((event) => {
      if (!editor.state.text.startsWith("!") || strokeOf(event) !== "enter" || vim?.pending(editor)) return false;
      if (running) return true;
      void execute().catch((error: unknown) => ctx.notify("error", String(error)));
      return true;
    }, "beforeKeymap");
    return () => extension.dispose();
  });
}
