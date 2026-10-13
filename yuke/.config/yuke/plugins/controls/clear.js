//! Add /clear as an alias for the built-in /new command.

/** Provide `/clear` while the built-in new-chat command is available. */
/** Register the clear alias when TUI exists. The context owns registrations; a host failure throws. @param {import("yuke").Context} ctx */
export default function (ctx) {
  const tui = ctx.get("tui");
  if (!tui) return;
  tui.command.add("clear", {
    desc: "leave the session and start empty",
    slash: true,
    when: () => tui.command.available("chat:new"),
    run: () => tui.command.perform("chat:new"),
  });
}
