import type { PluginContext } from "yuke:plugins";

/** Show the version of the running host. The native context owns the build identity. */
export function apply(ctx: PluginContext): undefined {
  const tui = ctx.get("tui");
  if (tui === undefined) return;
  const version = ctx.version.replace(/\.b\d{14}$/, "").replace(/\+([0-9a-f]{8})[0-9a-f]+(?=\.dirty$|$)/, "+$1");
  tui.status.set("version", { text: `yuke ${version}`, side: "right", order: 100, priority: 5 });
}
