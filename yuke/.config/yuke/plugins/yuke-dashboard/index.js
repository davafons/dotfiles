//! Show startup actions in the empty chat pane.
import { env, fs } from "yuke";
import { ChatView } from "yuke:chat";
import { currentPane } from "yuke:session";
import { Text, clip, measure, text } from "yuke:ui";
/** @import { Rect, ViewLike } from "yuke:ui" */
/** @typedef {{ label: string, key: string, command: string }} Action */
/** @typedef {{ text: string, x: number, y: number, group: string }} DrawText */

const LOGO = [
  "██╗   ██╗██╗   ██╗██╗  ██╗███████╗",
  "╚██╗ ██╔╝██║   ██║██║ ██╔╝██╔════╝",
  " ╚████╔╝ ██║   ██║█████╔╝ █████╗  ",
  "  ╚██╔╝  ██║   ██║██╔═██╗ ██╔══╝  ",
  "   ██║   ╚██████╔╝██║  ██╗███████╗",
  "   ╚═╝    ╚═════╝ ╚═╝  ╚═╝╚══════╝",
];
/** @type {Action[]} */
const ACTIONS = [
  { label: "Resume a session", key: "r", command: "ui:sessions" },
  { label: "Search chats and files", key: "s", command: "search:open" },
  { label: "Project tasks and checkpoints", key: "w", command: "project-work:work" },
  { label: "Choose a model", key: "m", command: "model:pick" },
  { label: "Commands", key: "c", command: "ui:palette" },
  { label: "Quit Yuke", key: "q", command: "quit" },
];

class Dashboard extends Text {
  /** @param {Action[]} actions */
  constructor(actions) {
    super();
    this.actions = actions;
    this.workspace = "workspace";
    this.cachedWorkspace = "";
    this.cachedText = "";
    this.width = -1;
    this.height = -1;
    this.menuX = 0;
    this.menuY = 0;
    this.menuWidth = 0;
    this.menuCount = 0;
    /** @type {DrawText[]} */
    this.rows = [];
  }

  /** @param {Rect} rect */
  layout(rect) {
    this.rect = rect;
    if (this.width === rect.w && this.height === rect.h && this.cachedText === this.text && this.cachedWorkspace === this.workspace) return;
    this.build();
  }

  build() {
    const { w, h } = this.rect;
    this.width = w;
    this.height = h;
    this.cachedText = this.text;
    this.cachedWorkspace = this.workspace;
    this.rows.length = 0;
    this.menuCount = 0;
    if (w <= 0 || h <= 0) return;
    const width = Math.min(54, w);
    const left = Math.floor((w - width) / 2);
    const logo = w >= 40 && h >= this.actions.length + 14 ? LOGO : ["YUKE"];
    const details = h >= logo.length + this.actions.length + 6;
    const footer = h >= logo.length + this.actions.length + 3;
    const height = logo.length + 1 + (details ? 3 : 0) + this.actions.length + (footer ? 2 : 0);
    let y = Math.max(0, Math.floor((h - height) / 2));
    for (let i = 0; i < logo.length && y < h; i++, y++) {
      const line = clip(logo[i] || "", width);
      this.rows.push({ text: line, x: left + Math.floor((width - measure(line)) / 2), y, group: "DashboardLogo" });
    }
    y++;
    if (details) {
      const home = env.get("HOME");
      const path = home && this.workspace.startsWith(home + "/") ? "~" + this.workspace.slice(home.length) : this.workspace;
      const context = [path, this.text.split("\n", 1)[0] || "no model yet"];
      for (let i = 0; i < context.length; i++, y++) {
        const line = clip(context[i] || "", width);
        this.rows.push({ text: line, x: left + Math.floor((width - measure(line)) / 2), y, group: "DashboardContext" });
      }
      y++;
    }
    this.menuX = left;
    this.menuY = y;
    this.menuWidth = width;
    for (let i = 0; i < this.actions.length && y < h; i++, y++) {
      const action = /** @type {Action} */ (this.actions[i]);
      const key = clip(action.key, width);
      const keyWidth = measure(key);
      const label = clip(action.label, Math.max(0, width - keyWidth - 2));
      this.rows.push({ text: label, x: left, y, group: "DashboardAction" });
      this.rows.push({ text: key, x: left + width - keyWidth, y, group: "DashboardKey" });
      this.menuCount++;
    }
    if (footer && y + 1 < h) {
      const line = clip("i: type a prompt · Esc: normal · c: commands", width);
      this.rows.push({ text: line, x: left + Math.floor((width - measure(line)) / 2), y: y + 1, group: "DashboardContext" });
    }
  }

  draw() {
    for (let i = 0; i < this.rows.length; i++) {
      const row = /** @type {DrawText} */ (this.rows[i]);
      text(this.rect.x + row.x, this.rect.y + row.y, row.text, row.group);
    }
  }
}

/** An empty-session dashboard that requires Composer Vim. Letters run existing commands only in an empty normal-mode composer. Missing optional commands have no row or key. */
/** Preserve the personal yuke-dashboard workflow with the one Vim service. No TUI or editor skips it; host failures throw. @param {import("yuke").Context} ctx */
export default function (ctx) {
  const tui = ctx.get("tui"), vim = ctx.get("composer-vim");
  if (!tui || !vim) return;
  tui.style.set({
    DashboardLogo: { fg: "accent", bold: true },
    DashboardAction: { fg: "strongFg" },
    DashboardKey: { fg: "accent" },
    DashboardContext: { link: "UIDim" },
  }, { default: true });
  const actions = ACTIONS.filter((action) => tui.command.available(action.command));
  /** @type {Map<ChatView, { title: Text, hint: Text, dashboardTitle: Text, dashboard: Dashboard, session: ChatView["session"], sessionId: string | null }>} */
  const panes = new Map();
  let workspace = "workspace";
  const sharedKeymap = /** @type {typeof tui.keymap} */ (Object.getPrototypeOf(tui.keymap));
  /** @type {(() => void) | null} */
  let releaseKeys = null;
  /** @type {(() => void) | null} */
  let releaseText = null;
  /** @type {(() => void) | null} */
  let releaseImages = null;

  const syncKeys = () => {
    const pane = currentPane();
    const normalDraft = ctx.alive && pane instanceof ChatView && panes.has(pane) && pane === tui.root.active &&
      pane.focus === "composer" && !pane.session.sessionId && pane.transcript.isEmpty() &&
      vim.mode(pane.composer) === "normal";
    if (normalDraft) {
      if (!releaseText) {
        releaseText = ctx.on("composer.changed", syncKeys);
        releaseImages = ctx.on("composer.attached", syncKeys);
      }
    } else if (releaseText) {
      releaseText(); releaseText = null;
      if (releaseImages) { releaseImages(); releaseImages = null; }
    }
    const enabled = normalDraft && pane instanceof ChatView && !pane.composer.text && !pane.composer.hasImages();
    if (!enabled) {
      if (releaseKeys) { releaseKeys(); releaseKeys = null; }
      return;
    }
    if (releaseKeys) return;
    releaseKeys = ctx.advise(sharedKeymap, "onKey", "around", (next, ev) => {
      if (tui.root.focused === tui.root.active && !sharedKeymap.owns() &&
          ev.type === "key" && ev.event !== "release" && ev.code === "char" && ev.mods === 0) {
        for (let i = 0; i < actions.length; i++) {
          const action = /** @type {Action} */ (actions[i]);
          if (action.key === ev.char) return tui.command.perform(action.command);
        }
      }
      return next(ev);
    }, { order: -100 });
  };

  /** @param {ViewLike} pane */
  const attach = (pane) => {
    if (!(pane instanceof ChatView)) return;
    const saved = panes.get(pane);
    const fresh = !saved || saved.session !== pane.session || saved.sessionId !== pane.session.sessionId;
    if (!saved) {
      const dashboard = new Dashboard(actions);
      dashboard.workspace = workspace;
      const dashboardTitle = new Text();
      panes.set(pane, { title: pane.title, hint: pane.hint, dashboardTitle, dashboard, session: pane.session, sessionId: pane.session.sessionId });
      pane.title = dashboardTitle;
      pane.hint = dashboard;
      tui.root.invalidate();
    } else {
      saved.session = pane.session;
      saved.sessionId = pane.session.sessionId;
    }
    if (fresh && !pane.session.sessionId && pane.transcript.isEmpty() && !pane.composer.text && !pane.composer.hasImages()) {
      vim.setMode(pane.composer, "normal");
    }
    syncKeys();
  };
  const newCommand = tui.command.map["chat:new"];
  if (newCommand) ctx.advise(newCommand, "run", "after", () => {
    const pane = currentPane();
    if (pane) attach(pane);
  });
  ctx.on("pane.focused", attach);
  ctx.on("pane.closed", (pane) => { if (pane instanceof ChatView) panes.delete(pane); syncKeys(); });
  ctx.on("region.focused", syncKeys);
  ctx.on("session.current.changed", () => {
    const pane = currentPane();
    if (pane instanceof ChatView) attach(pane);
    else syncKeys();
  });
  ctx.on("composer-vim:mode", syncKeys);
  ctx.on("ui.started", () => {
    actions.length = 0;
    for (let i = 0; i < ACTIONS.length; i++) {
      const action = /** @type {Action} */ (ACTIONS[i]);
      if (tui.command.available(action.command)) actions.push(action);
    }
    panes.forEach(saved => { saved.dashboard.width = -1; });
    tui.root.invalidate();
  });
  const leaves = tui.root.root_node?.leaves() || [];
  for (let i = 0; i < leaves.length; i++) {
    const shape = leaves[i]?.shape;
    if (shape?.type === "leaf") attach(shape.view);
  }
  ctx.own(() => {
    if (releaseKeys) { releaseKeys(); releaseKeys = null; }
    if (releaseText) { releaseText(); releaseText = null; }
    if (releaseImages) { releaseImages(); releaseImages = null; }
    panes.forEach((saved, pane) => {
      if (pane.title === saved.dashboardTitle) pane.title = saved.title;
      if (pane.hint === saved.dashboard) pane.hint = saved.hint;
    });
    panes.clear();
    tui.root.invalidate();
  });
  fs.stat(".").then((directory) => {
    if (!ctx.alive || !directory?.isDirectory) return;
    workspace = directory.path.replace(/[\x00-\x1f\x7f-\x9f]/gu, " ");
    panes.forEach((saved) => { saved.dashboard.workspace = workspace; });
    tui.root.invalidate();
  }).catch(() => {});

  ctx.on("chat.press", (pane, ev) => {
    if (pane.session.sessionId || !pane.transcript.isEmpty()) return;
    const dashboard = panes.get(pane)?.dashboard;
    if (!dashboard) return;
    const row = ev.row - dashboard.rect.y - dashboard.menuY;
    const col = ev.col - dashboard.rect.x - dashboard.menuX;
    if (row < 0 || row >= dashboard.menuCount || col < 0 || col >= dashboard.menuWidth) return;
    tui.root.focusView(pane);
    const action = dashboard.actions[row];
    return action ? tui.command.perform(action.command) : false;
  });
}
