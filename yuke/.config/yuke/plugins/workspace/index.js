//! Workspace commands use the core transition and leave session ownership to the session layer.
import { workspace } from "yuke";
import { currentPane } from "yuke:session";

/** Register workspace commands when TUI exists. Missing TUI skips registration; invalid registrations throw. @param {import("yuke").Context} ctx */
export default function (ctx) {
  const tui = ctx.get("tui");
  if (!tui) return;
  tui.command.add("pwd", {
    desc: "show the current workspace",
    slash: "pwd",
    run: () => ctx.interaction.notify(workspace.path),
  });
  tui.command.add("cd", {
    desc: "continue this conversation in another workspace",
    slash: "cd",
    args: true,
    run: (/** @type {string | undefined} */ query) => {
      const argument = query?.trim();
      if (!argument) return ctx.interaction.notify(workspace.path);
      const quote = argument[0];
      const path = argument.length > 1 && (quote === '"' || quote === "'" || quote === "`") && argument[argument.length - 1] === quote ? argument.slice(1, -1) : argument;
      const pane = currentPane();
      if (!pane || pane.session.creating) return ctx.interaction.notify("cd refused: wait for the chat to open", "warn");
      if (tui.root.root_node?.shape.type !== "leaf") return ctx.interaction.notify("cd refused: close the other panes first", "warn");
      const composer = pane.composer;
      const draft = composer?.text.trim() ?? "";
      const commandPath = /^\/cd\s+([\s\S]*)$/.exec(draft)?.[1]?.trim();
      if (composer?.hasImages() || (draft && commandPath !== argument)) return ctx.interaction.notify("cd refused: save or clear the draft first", "warn");
      workspace.requestChange(path, pane.session.sessionId);
    },
  });
}
