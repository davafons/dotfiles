//! Show the version embedded in this running Yuke, not another binary on PATH.
import { client } from "yuke";
import { versionLabel } from "./version-label.js";

/** A cached build label from the running engine. It stays unchanged when the binary on disk is replaced. */
/** Register the personal build-status surface when TUI exists. The context owns registrations; a host failure throws. @param {import("yuke").Context} ctx */
export default function (ctx) {
  const tui = ctx.get("tui");
  if (!tui) return;
  let label = "";
  tui.status.add({ side: "right", order: 100, render: () => label });
  void client.request("initialize").then((result) => {
    if (!ctx.alive) return;
    label = "yuke " + versionLabel(result.engine.version);
    tui.root.invalidatePaint();
  }).catch((error) => {
    if (!ctx.alive) return;
    label = "yuke build unknown";
    ctx.print("Cannot read the running Yuke build", error);
    tui.root.invalidatePaint();
  });
}
