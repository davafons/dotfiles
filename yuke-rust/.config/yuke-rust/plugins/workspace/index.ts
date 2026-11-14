import { stat } from "yuke:fs";
import type { PluginContext } from "yuke:plugins";
import { Command, env } from "yuke:process";
import { Transcript } from "yuke:transcript";
import { command } from "../../lib.ts";

/** Add /cd and /pwd. A workspace switch forks saved history with destination instructions. A busy pane refuses it. */
export function apply(ctx: PluginContext): undefined {
  const tui = ctx.get("tui");
  if (tui === undefined) return;
  const chat = ctx.get("chat");
  const sessions = ctx.get("sessions");
  command(ctx, tui, "pwd", "Show the current workspace", () => {
    const pane = tui.panes.active;
    ctx.notify("info", pane === undefined ? tui.startup.cwd : (chat.folder(pane.view) ?? tui.startup.cwd));
  });
  let changing = false;
  command(
    ctx,
    tui,
    "cd",
    "Continue this conversation in another workspace",
    async (argument) => {
      if (changing) throw new Error("A workspace change already runs.");
      const pane = tui.panes.active;
      if (pane === undefined || chat.folder(pane.view) === undefined) throw new Error("Focus a chat pane first.");
      const current = chat.folder(pane.view) ?? tui.startup.cwd;
      let path = argument.trim();
      if (path === "") {
        ctx.notify("info", current);
        return;
      }
      const first = path[0];
      if ((first === '"' || first === "'" || first === "`") && path.at(-1) === first) path = path.slice(1, -1);
      if (path === "~" || path.startsWith("~/")) {
        const home = env.get("HOME");
        if (home === undefined) throw new Error("HOME is not set.");
        path = home + path.slice(1);
      }
      changing = true;
      const controller = new AbortController();
      const signal = AbortSignal.any([ctx.signal, controller.signal]);
      try {
        const resolved = await new Command("python3", {
          args: ["-c", "from pathlib import Path; import sys; print(Path(sys.argv[1]).resolve(strict=True))", path],
          cwd: current,
          signal,
        }).output();
        if (!resolved.success) throw new Error(new TextDecoder().decode(resolved.stderr));
        const target = new TextDecoder().decode(resolved.stdout).trim();
        if (!(await stat(target, { signal })).isDirectory) throw new Error("The destination is not a directory.");
        if (target === current) return;
        if (
          new Set(
            tui.widgets
              .list()
              .map((mount) => mount.pane)
              .filter((item) => item !== undefined),
          ).size !== 1
        )
          throw new Error("Keep one pane before changing workspace.");
        const id = chat.session(pane.view);
        if (id === undefined) chat.newSession({ cwd: target });
        else {
          const transcript = new Transcript();
          const handle = await sessions.open(id, { tail: 0, signal, onEvent: (event) => transcript.apply(event) });
          if (transcript.state !== "idle" || transcript.pending.size !== 0 || handle.jobs().length !== 0)
            throw new Error("Wait for the turn, queued input, and background work to end before changing workspace.");
          const fork = await sessions.fork(id, { cwd: target });
          if (tui.panes.active !== pane || chat.session(pane.view) !== id)
            throw new Error(`The pane changed. The fork is saved as ${fork}.`);
          await chat.show(fork);
        }
        ctx.notify("info", `Workspace: ${target}`);
      } finally {
        controller.abort();
        changing = false;
      }
    },
    "<path>",
  );
}
