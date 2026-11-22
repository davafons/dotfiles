import { readTextFile } from "yuke:fs";
import type { PluginContext, SessionContext } from "yuke:plugins";
import { strokeOf, TextEditor } from "yuke:tui";
import type { PersonalCommands } from "../../lib.ts";

/** Route personal slash commands through public composer extensions. No TUI means no key handler. */
export function apply(ctx: PluginContext): undefined {
  const commands = new Map<string, (argument: string) => void | Promise<void>>();
  const service: PersonalCommands = {
    add: (name, run) => {
      if (commands.has(name)) throw new Error(`Duplicate personal command: ${name}`);
      commands.set(name, run);
      return () => {
        if (commands.get(name) === run) commands.delete(name);
      };
    },
  };
  ctx.provide("personal-commands", service);
  const tui = ctx.get("tui");
  if (tui === undefined) return;
  tui.widgets.addWatcher((mount) => {
    const editor = mount.widget;
    if (!(editor instanceof TextEditor) || editor.role !== "composer") return;
    const extension = editor.extend(mount.signal);
    extension.addKeyHandler((event) => {
      const text = editor.state.text;
      if (!text.startsWith("/") || strokeOf(event) !== "enter" || ctx.get("composer-vim")?.pending(editor))
        return false;
      const match = /^\/([^\s:]+)(?:\s+([\s\S]*))?$/.exec(text);
      const name = match?.[1];
      const run = name === undefined ? undefined : commands.get(name);
      if (run === undefined) return false;
      const draft = editor.state;
      editor.reset({ text: "", selection: { anchor: 0, head: 0 }, spans: [] });
      Promise.resolve()
        .then(() => run(match?.[2] ?? ""))
        .catch((error: unknown) => {
          if (ctx.signal.aborted || mount.signal.aborted) return;
          if (editor.state.text === "") editor.restore(draft);
          ctx.notify("error", String(error));
        });
      return true;
    }, "beforeKeymap");
    return () => extension.close();
  });
}

/** Add the personal base prompt to each session. File or JSON errors stop this plugin for the session. */
export async function session(s: SessionContext): Promise<undefined> {
  const prompt: unknown = JSON.parse(await readTextFile(`${import.meta.dirname}/prompt.json`));
  if (typeof prompt !== "string") throw new TypeError("The personal prompt must be text.");
  s.addHook("prompt.build", (event) => ({ sections: { ...event.sections, base: prompt } }));
}
