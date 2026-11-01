import { stat } from "yuke:fs";
import type { PluginContext } from "yuke:plugins";
import { env } from "yuke:process";
import type { Navigation, NavigationBridge } from "../../navigation.ts";

/** Share session navigation and file opening. A bridge owns the external application connection. */
export function apply(ctx: PluginContext): undefined {
  const tui = ctx.get("tui");
  const chat = ctx.get("chat");
  let bridge: NavigationBridge | undefined;
  const service: Navigation = {
    installBridge: (next) => {
      bridge = next;
      return () => {
        if (bridge === next) bridge = undefined;
      };
    },
    openSession: async (id) => {
      try {
        await chat.show(id);
      } catch (error) {
        if (bridge === undefined || !(await bridge.focusSession(id))) throw error;
      }
    },
    openFile: async (path, line, column) => {
      const pane = tui?.panes.active;
      const cwd = pane === undefined ? tui?.startup.cwd : chat.folder(pane.view);
      if (cwd === undefined) throw new Error("Focus a chat pane to open its file reference.");
      const home = env.get("HOME");
      if (path.startsWith("~/") && home !== undefined) path = home + path.slice(1);
      if (!(await stat(path, { baseDir: cwd, signal: ctx.signal })).isFile)
        throw new Error("The reference is not a file.");
      if (bridge === undefined) throw new Error("Open this Yuke in Herdr to open files in Code.");
      const absolute = path.startsWith("/") ? path : `${cwd}/${path}`;
      const url = new URL(`file://${absolute.split("/").map(encodeURIComponent).join("/")}`);
      if (line !== undefined) url.hash = `L${line}${column === undefined ? "" : `C${column}`}`;
      await bridge.openFile(url.href, cwd);
    },
  };
  ctx.provide("personal-navigation", service);
}
