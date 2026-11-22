import type { PluginContext } from "yuke:plugins";
import type { SessionId } from "yuke:protocol";
import { TextEditor, type Tui } from "yuke:tui";

export const EMPTY = { text: "", selection: { anchor: 0, head: 0 }, spans: [] } as const;

export interface PersonalCommands {
  add: (name: string, run: (argument: string) => void | Promise<void>) => () => void;
}

declare module "yuke:plugins" {
  interface Services {
    readonly "personal-commands": PersonalCommands;
  }
}

/** The focused composer, including the composer of a draft. */
export function focusedEditor(tui: Tui): TextEditor | undefined {
  const focused = tui.focusedView;
  return focused instanceof TextEditor && focused.role === "composer" ? focused : undefined;
}

/** The session in the active chat pane. A new draft has none. */
export function currentSession(ctx: Pick<PluginContext, "get">, tui: Tui): SessionId | undefined {
  const pane = tui.panes.activePane;
  return pane === undefined ? undefined : ctx.get("chat").sessionIdOf(pane.view);
}

/** Add a slash alias with arguments and a menu command. Both registrations end with the plugin. */
export function command(
  ctx: Pick<PluginContext, "get" | "signal">,
  tui: Tui,
  name: string,
  description: string,
  run: (args: string) => void | Promise<void>,
  argumentHint?: string,
): void {
  // The slash word gives the command a `/name` completion. The personal key handler still runs the draft.
  tui.commands.add({
    name,
    description,
    slash: name,
    ...(argumentHint === undefined ? {} : { argumentHint }),
    run: (args) => run(typeof args === "string" ? args : ""),
  });
  const remove = ctx.get("personal-commands").add(name, run);
  ctx.signal.addEventListener("abort", remove, { once: true });
}
