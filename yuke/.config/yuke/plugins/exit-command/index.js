//! Slash commands that use Yuke's graceful quit path.
import { quit } from "yuke:ui";

/** Register /exit and /close in the TUI. Quit guards can hold the exit. */
/** Register the personal exit-command surface when TUI exists. The context owns registrations; a host failure throws. @param {import("yuke").Context} ctx */
export default function (ctx) {
  const tui = ctx.get("tui");
  if (!tui) return;
  tui.command.add("exit", {
    desc: "exit Yuke",
    slash: true,
    run: quit,
  });
  tui.command.add("close", {
    desc: "exit Yuke (alias)",
    slash: true,
    run: quit,
  });
}
