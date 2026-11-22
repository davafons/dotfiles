import type { PluginContext } from "yuke:plugins";
import { strokeOf, TextEditor } from "yuke:tui";
import { command, EMPTY } from "../../lib.ts";
import type {} from "../vim/src/service.ts";

/** Add personal quit, clear, interrupt, and pane controls. The TUI owns registrations. */
export function apply(ctx: PluginContext): undefined {
  const tui = ctx.get("tui");
  const vim = ctx.get("composer-vim");
  if (tui === undefined || vim === undefined) return;
  const run = (name: string): void => {
    tui.commands.run(`core:${name}`);
  };
  // Ctrl+K moves pane focus, so btw's own ctrl+k b chord never reaches its second stroke.
  tui.keys.add("ctrl+x b", "btw:ask", { in: "chat" });
  for (const name of ["exit", "close"]) command(ctx, tui, name, "Exit Yuke", () => run("quit"));
  command(ctx, tui, "clear", "Start an empty chat", () => ctx.get("chat").newSession());
  command(
    ctx,
    tui,
    "panel",
    "Split, close, or keep the current panel",
    (argument) => {
      switch (argument.trim()) {
        case "split":
          run("split-down");
          break;
        case "vsplit":
          run("split-right");
          break;
        case "close":
          run("close");
          break;
        case "only": {
          const active = tui.panes.activePane;
          const panes = new Set(tui.widgets.list().map((mount) => mount.pane));
          panes.forEach((pane) => {
            if (pane !== undefined && pane !== active) pane.close();
          });
          break;
        }
        default:
          ctx.notify("info", "Usage: /panel split | vsplit | close | only");
      }
    },
    "<split|vsplit|close|only>",
  );
  let armed: TextEditor | undefined;
  let removeExitStatus: (() => void) | undefined;
  const disarm = (): void => {
    armed = undefined;
    removeExitStatus?.();
    removeExitStatus = undefined;
  };
  tui.addFocusListener(disarm);
  ctx.get("chat").addChangeListener(disarm);
  tui.widgets.addWatcher((mount) => {
    const editor = mount.widget;
    if (!(editor instanceof TextEditor) || editor.role !== "composer") return;
    const extension = editor.extend(mount.signal);
    extension.addMouseHandler(() => {
      disarm();
      return false;
    });
    extension.addPasteHandler(() => {
      disarm();
      return false;
    });
    extension.addChangeListener(disarm);
    extension.addKeyHandler((event) => {
      const stroke = strokeOf(event);
      if (stroke !== "ctrl+c") {
        disarm();
        const direction = ({ "ctrl+h": "left", "ctrl+k": "up", "ctrl+l": "right" } as const)[
          stroke as "ctrl+h" | "ctrl+k" | "ctrl+l"
        ];
        if (direction !== undefined || (stroke === "ctrl+j" && vim.mode(editor) !== "insert")) {
          vim.cancel(editor);
          tui.panes.moveFocus(direction ?? "down");
          return true;
        }
        return false;
      }
      if (editor.state.text !== "") {
        editor.reset(EMPTY);
        vim.setMode(editor, "normal");
      } else if (vim.mode(editor) === "insert") {
        disarm();
        vim.setMode(editor, "normal");
      } else if (armed === editor) {
        disarm();
        run("quit");
      } else {
        tui.commands.run("chat:interrupt");
        armed = editor;
        removeExitStatus = tui.status.set("exit", {
          text: "press Ctrl+C again to exit",
          side: "left",
          order: -1,
          priority: 100,
        });
      }
      return true;
    }, "beforeKeymap");
    return () => {
      if (armed === editor) disarm();
      extension.close();
    };
  });
}
