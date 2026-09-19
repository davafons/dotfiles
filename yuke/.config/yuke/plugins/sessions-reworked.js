//! Replace the built-in session finder with a scoped two-panel session browser.
import { client, env, exec, fs } from "yuke";
import { Transcript } from "yuke:chat";
import { currentEntry, currentPane, sessions, showSession } from "yuke:session";
import { Picker, Text, Window, clip, text } from "yuke:ui";
/** @import { Plugin, InjectContext } from "yuke" */

const PAGE_LIMIT = 100;
const HISTORY_LIMIT = 8;
const MAX_PAGES = 1000;
const CONTEXT_LIMIT = 50;
const CONTEXT_WORKERS = 4;
const ONE_SECOND = Object.freeze({ periodMs: 1000 });
const EMPTY_RECT = Object.freeze({ x: 0, y: 0, w: 0, h: 0 });
const LOCK_PROBE = `
import fcntl
import os
import sys

root = sys.argv[1]
for session_id in sys.argv[2:]:
    path = os.path.join(root, session_id + ".lock")
    if not os.path.exists(path):
        continue
    try:
        lock = open(path, "a+b")
    except OSError:
        continue
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print(session_id)
    finally:
        lock.close()
`;

/** @param {unknown} error @returns {string} */
function errorText(error) {
  return error !== null && typeof error === "object" && "message" in error ? String(error.message) : String(error);
}

/** @param {number} timestamp @param {number} [now] @returns {string} */
function ageLabel(timestamp, now = Date.now()) {
  const seconds = Math.max(0, Math.floor((now - timestamp) / 1000));
  if (seconds < 60) return seconds + "s ago";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return minutes + "m ago";
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return hours + "h ago";
  const days = Math.floor(hours / 24);
  if (days < 30) return days + "d ago";
  const months = Math.floor(days / 30);
  if (months < 12) return months + "mo ago";
  return Math.floor(days / 365) + "y ago";
}

/** @param {Wire.Session} session @returns {string} */
function titleOf(session) {
  const title = session.title.trim();
  return title || session.name?.trim() || "Untitled session";
}

/** @param {Wire.SessionActivity} activity @returns {string} */
function activityLabel(activity) {
  const state = activity.state;
  let label;
  if (state.type === "idle") label = "idle";
  else if (state.type === "running_tool") label = "tool · " + state.tool_name;
  else if (state.type === "retrying") label = "retry " + state.attempt + "/" + state.max_attempts;
  else label = state.type.replace("_", " ");
  if (activity.queued > 0) label += " · " + activity.queued + " queued";
  return label;
}

/** @param {string} path @returns {string} */
function workspaceLabel(path) {
  const clean = path.replace(/\/+$/, "");
  const slash = clean.lastIndexOf("/");
  return clean.slice(slash + 1) || clean || "/";
}

/** @param {string} selector @returns {string} */
function modelLabel(selector) {
  const slash = selector.lastIndexOf("/");
  return slash < 0 ? selector : selector.slice(slash + 1);
}

/** @param {Wire.Session} session @returns {boolean} */
function hasGenericTitle(session) {
  const title = titleOf(session).toLowerCase();
  const workspace = workspaceLabel(session.root).toLowerCase();
  return title === "yuke" || title === "untitled session" || title === "new chat" || title === workspace;
}

/** Summarize the newest user-authored prompt in one line. @param {readonly Wire.Message[]} messages @returns {string} */
function promptContext(messages) {
  for (let i = messages.length - 1; i >= 0; i--) {
    const message = messages[i];
    if (message.type !== "user" || message.source) continue;
    const parts = message.content.map((part) => {
      if (part.type === "text") return part.text;
      if (part.type === "image") return "[image]";
      if (part.type === "audio") return "[audio]";
      return part.filename ? "[file: " + part.filename + "]" : "[file]";
    });
    return parts.join("").replace(/\s+/gu, " ").trim();
  }
  return "";
}

/** Resolve the directory Yuke was launched in for a draft with no current session. @returns {Promise<string | null>} */
async function launchWorkspace() {
  try {
    const directory = await fs.stat(".");
    return directory?.isDirectory ? directory.path : null;
  } catch {
    return null;
  }
}

/** Quote one argument for the host shell. @param {string} value @returns {string} */
function shellArg(value) {
  return "'" + value.replaceAll("'", "'\"'\"'") + "'";
}

/** Resolve the sibling directory that holds the durable session ownership locks. @returns {string | null} */
function ownerDirectory() {
  const home = env.get("HOME");
  const base = env.get("XDG_DATA_HOME") || (home ? home + "/.local/share" : "");
  if (!base) return null;
  return base.replace(/\/+$/, "") + "/" + (env.get("YUKE_APPNAME") || "yuke") + "/yuke.db.owners";
}

/** Find whether each session is closed, open here, or open in another Yuke process. @param {Wire.SessionListItem[]} items @returns {Promise<Map<string, "closed" | "here" | "elsewhere">>} */
async function sessionOwnership(items) {
  /** @type {Map<string, "closed" | "here" | "elsewhere">} */
  const ownership = new Map(items.map((item) => [item.session.id, "closed"]));
  const heldHere = new Set(sessions.map((session) => session.sessionId).filter((id) => id !== null));
  for (const id of heldHere) ownership.set(id, "here");
  const directory = ownerDirectory();
  if (!directory || items.length === 0) return ownership;
  const command = ["python3", "-c", LOCK_PROBE, directory, ...items.map((item) => item.session.id)].map(shellArg).join(" ");
  const result = await exec(command, { timeoutMs: 5000 });
  if (result.code !== 0) throw new Error("Cannot inspect session owners: " + (result.stderr.trim() || "lock probe exited " + result.code));
  for (const id of result.stdout.split(/\r?\n/).filter(Boolean)) {
    ownership.set(id, heldHere.has(id) ? "here" : "elsewhere");
  }
  return ownership;
}

/** Read every top-level session page. Child agent sessions stay in the agent picker. @returns {Promise<Wire.SessionListItem[]>} */
async function listSessions() {
  /** @type {Wire.SessionListItem[]} */
  const items = [];
  const cursors = new Set();
  /** @type {string | undefined} */
  let cursor;
  for (let pageIndex = 0; pageIndex < MAX_PAGES; pageIndex++) {
    const page = await client.sessionList({ population: { type: "top_level" }, limit: PAGE_LIMIT, ...(cursor ? { cursor } : {}) });
    items.push(...page.items);
    if (!page.next_cursor) return items;
    if (cursors.has(page.next_cursor)) throw new Error("The session page cursor did not advance.");
    cursors.add(page.next_cursor);
    cursor = page.next_cursor;
  }
  throw new Error("The session list exceeds " + MAX_PAGES + " pages.");
}

/** Read backward until the latest user prompt is present. @param {string} sessionId @returns {Promise<readonly Wire.Message[]>} */
async function recentHistory(sessionId) {
  /** @type {Wire.Message[]} */
  const messages = [];
  const cursors = new Set();
  let before = 0;
  for (let pageIndex = 0; pageIndex < MAX_PAGES; pageIndex++) {
    const page = await client.request("session.history", { session_id: sessionId, before_message_id: before, limit: HISTORY_LIMIT });
    messages.unshift(...page.messages);
    if (page.messages.some((message) => message.type === "user") || !page.has_more) return messages;
    const next = page.messages[0]?.id;
    if (next == null || cursors.has(next)) throw new Error("The session history cursor did not advance.");
    cursors.add(next);
    before = next;
  }
  throw new Error("The recent session history exceeds " + MAX_PAGES + " pages.");
}

/** Build a themed transcript from the last prompt through the newest answer. @param {readonly Wire.Message[]} messages @returns {Transcript} */
function historyTranscript(messages) {
  let start = -1;
  for (let i = messages.length - 1; i >= 0; i--) {
    if (messages[i].type === "user") { start = i; break; }
  }
  if (start < 0) start = Math.max(0, messages.length - 2);
  const recent = messages.slice(start);
  /** @type {Map<number, (Wire.AssistantPart | (Wire.ContentPart & { id: number }))[]>} */
  const parts = new Map();
  /** @type {Parameters<Transcript["setOutline"]>[0]} */
  const outline = [];
  for (let i = 0; i < recent.length; i++) {
    const message = recent[i];
    if (message.type === "user") {
      parts.set(message.id, message.content.map((part, id) => ({ ...part, id })));
      outline.push({ id: message.id, type: "user", ...(message.source ? { source: message.source } : {}), ...(message.skill_name ? { skill_name: message.skill_name } : {}) });
    } else if (message.type === "assistant") {
      parts.set(message.id, message.content.slice());
      outline.push({ id: message.id, type: "assistant", ...(message.error ? { error: message.error } : {}) });
    } else {
      parts.set(message.id, [{ type: "text", id: 0, text: message.summary }]);
      outline.push({ id: message.id, type: "compaction" });
    }
  }
  const transcript = new Transcript({ partsOf: (id) => parts.get(id) || [] });
  transcript.setOutline(outline, null);
  transcript.pager.toBottom();
  return transcript;
}

class SessionBrowser {
  /** @param {InjectContext} ctx @param {Wire.SessionListItem[]} items @param {Map<string, Wire.SessionActivity>} live @param {Map<string, "closed" | "here" | "elsewhere">} ownership @param {string | null} workspace @param {string | null} currentId @param {"workspace" | "all"} initialScope */
  constructor(ctx, items, live, ownership, workspace, currentId, initialScope) {
    this.ctx = ctx;
    this.items = items;
    this.live = live;
    this.ownership = ownership;
    this.workspace = workspace;
    this.currentId = currentId;
    this.scope = workspace && initialScope === "workspace" ? "workspace" : "all";
    /** @type {import("yuke:ui").Rect} */
    this.rect = { ...EMPTY_RECT };
    /** @type {import("yuke:ui").Rect} */
    this.left = { ...EMPTY_RECT };
    /** @type {import("yuke:ui").Rect} */
    this.right = { ...EMPTY_RECT };
    this.title = new Text({ group: "UITitle" });
    this.notice = new Text({ group: "UIDim" });
    /** @type {Map<string, { state: "loading" } | { state: "ready", transcript: Transcript } | { state: "error", message: string }>} */
    this.previews = new Map();
    /** @type {Map<string, Promise<readonly Wire.Message[]>>} */
    this.histories = new Map();
    /** @type {Map<string, string>} */
    this.contexts = new Map();
    this.contextLoading = new Set();
    this.closed = false;
    this.picker = new Picker({
      items: this.scopeItems(),
      itemHeight: 3,
      key: (item) => item.session.id,
      filterText: (item) => {
        const session = item.session;
        return [session.title, session.name || "", session.model, session.reasoning, session.root, workspaceLabel(session.root), session.id, this.ownershipLabel(item), this.contexts.get(session.id) || ""].join(" ");
      },
      format: (item) => this.formatItem(item),
      validate: (item) => {
        if (this.ownershipOf(item) !== "elsewhere") return true;
        ctx.interaction.notify("That session is open in another Yuke and cannot be resumed here.", "warn");
        return false;
      },
      onMove: () => {
        this.loadSelected();
        ctx.tui.root.invalidatePaint();
      },
      onAccept: (item) => {
        const pane = currentPane();
        if (pane) showSession(pane, item.session.id);
      },
      keymap: {
        tab: () => this.toggleScope(),
        "ctrl+d": () => this.scrollPreview(1),
        "ctrl+u": () => this.scrollPreview(-1),
      },
      needsTick: ONE_SECOND,
    });
    const input = this.picker.input;
    if (input) {
      const refilter = input.onChange;
      input.onChange = () => {
        refilter?.();
        this.loadSelected();
        ctx.tui.root.invalidate();
      };
    }
    this.loadSelected();
    this.loadContexts();
  }

  /** @returns {Wire.SessionListItem[]} */
  scopeItems() {
    if (this.scope === "all" || !this.workspace) return this.items;
    return this.items.filter((item) => item.session.root === this.workspace);
  }

  /** @returns {string} */
  scopeLabel() {
    return this.scope === "workspace" && this.workspace ? "current · " + workspaceLabel(this.workspace) : "all workspaces";
  }

  /** @returns {string} */
  footer() {
    const scope = this.workspace ? (this.scope === "workspace" ? "tab all" : "tab current") + " · " : "";
    return scope + "ctrl+n/p sessions · ctrl+d/u preview · ↵ resume · esc close";
  }

  /** @param {Wire.SessionListItem} item @returns {"closed" | "here" | "elsewhere"} */
  ownershipOf(item) { return this.ownership.get(item.session.id) || "closed"; }

  /** @param {Wire.SessionListItem} item @returns {string} */
  ownershipLabel(item) {
    if (item.session.id === this.currentId) return "current";
    const ownership = this.ownershipOf(item);
    return ownership === "here" ? "open here" : ownership === "elsewhere" ? "open elsewhere" : "closed";
  }

  /** @param {Wire.SessionListItem} item @returns {Wire.SessionActivity} */
  activityOf(item) { return this.live.get(item.session.id) || item.activity; }

  /** @param {Wire.SessionListItem} item @returns {string} */
  stateLabel(item) {
    if (item.session.id === this.currentId) return "current";
    const ownership = this.ownershipOf(item);
    if (ownership === "elsewhere") return "open elsewhere";
    const activity = this.activityOf(item);
    if (activity.state.type !== "idle") return activityLabel(activity);
    return ownership === "here" ? "open here" : "closed";
  }

  /** @param {Wire.SessionListItem} item */
  formatItem(item) {
    const session = item.session;
    const activity = this.activityOf(item);
    const current = session.id === this.currentId;
    const ownership = this.ownershipOf(item);
    const active = ownership !== "elsewhere" && activity.state.type !== "idle";
    const context = this.contexts.get(session.id) || "";
    const generic = hasGenericTitle(session);
    const primary = generic && context ? context : titleOf(session);
    const badge = current ? "● CURRENT" : ownership === "elsewhere" ? "⊘ ELSEWHERE" : active ? "◆ WORKING" : ownership === "here" ? "● OPEN" : "○ CLOSED";
    const titleGroup = current ? "SessionCurrent" : ownership === "elsewhere" ? "SessionElsewhere" : active ? "SessionWorking" : "SessionTitle";
    const titleSelGroup = current ? "SessionCurrentSel" : ownership === "elsewhere" ? "SessionElsewhereSel" : active ? "SessionWorkingSel" : "SessionTitleSel";
    const contextLine = generic && context ? "session · " + titleOf(session) : context ? "↳ " + context : this.contextLoading.has(session.id) ? "↳ loading recent prompt…" : "↳ no user prompt";
    const count = session.message_count + (session.message_count === 1 ? " msg" : " msgs");
    const model = modelLabel(session.model || "no model");
    const location = this.scope === "all" ? workspaceLabel(session.root) + " · " + model : model;
    const detail = this.stateLabel(item) + " · " + count;
    return { lines: [
      { text: badge + "  " + primary, right: ageLabel(session.updated_at_ms), group: titleGroup, selGroup: titleSelGroup },
      { text: contextLine, group: "SessionContext", selGroup: "SessionContextSel" },
      { text: location, detail, group: "SessionMeta", selGroup: "SessionMetaSel" },
    ] };
  }

  toggleScope() {
    if (!this.workspace) return;
    this.scope = this.scope === "workspace" ? "all" : "workspace";
    this.picker.setSource(this.scopeItems());
    this.loadSelected();
    this.ctx.tui.root.invalidate();
  }

  /** @returns {{ state: "ready", transcript: Transcript } | null} */
  readyPreview() {
    const selected = this.picker.list.selected();
    if (!selected) return null;
    const preview = this.previews.get(selected.session.id);
    return preview?.state === "ready" ? preview : null;
  }

  /** @param {number} direction */
  scrollPreview(direction) {
    const preview = this.readyPreview();
    if (!preview) return;
    preview.transcript.pager.navPage(direction);
    this.ctx.tui.root.invalidatePaint();
  }

  /** Share one history request between the list context and right-side preview. @param {string} id @returns {Promise<readonly Wire.Message[]>} */
  historyFor(id) {
    let history = this.histories.get(id);
    if (!history) {
      history = recentHistory(id);
      this.histories.set(id, history);
    }
    return history;
  }

  /** @param {Wire.SessionListItem} item */
  async loadContext(item) {
    const id = item.session.id;
    if (this.contexts.has(id)) return;
    this.contextLoading.add(id);
    this.ctx.tui.root.invalidatePaint();
    try {
      const messages = await this.historyFor(id);
      if (!this.closed) this.contexts.set(id, promptContext(messages));
    } catch {
      if (!this.closed) this.contexts.set(id, "");
    } finally {
      this.contextLoading.delete(id);
      if (!this.closed) this.ctx.tui.root.invalidatePaint();
    }
  }

  loadContexts() {
    const queue = this.items.slice(0, CONTEXT_LIMIT);
    for (const item of queue) this.contextLoading.add(item.session.id);
    this.ctx.tui.root.invalidatePaint();
    let next = 0;
    const worker = async () => {
      while (!this.closed && next < queue.length) await this.loadContext(queue[next++]);
    };
    for (let i = 0; i < Math.min(CONTEXT_WORKERS, queue.length); i++) void worker();
  }

  loadSelected() {
    const selected = this.picker.list.selected();
    if (!selected || this.previews.has(selected.session.id)) return;
    const id = selected.session.id;
    this.previews.set(id, { state: "loading" });
    this.historyFor(id).then((messages) => {
      if (this.closed) return;
      this.previews.set(id, { state: "ready", transcript: historyTranscript(messages) });
      this.ctx.tui.root.invalidate();
    }, (error) => {
      if (this.closed) return;
      this.previews.set(id, { state: "error", message: errorText(error) });
      this.ctx.tui.root.invalidate();
    });
  }

  /** @param {import("yuke:ui").Rect} rect */
  layout(rect) {
    this.rect = rect;
    const gap = rect.w >= 72 ? 3 : 0;
    const leftWidth = gap ? Math.max(36, Math.floor((rect.w - gap) * 0.5)) : rect.w;
    this.left = { x: rect.x, y: rect.y, w: leftWidth, h: rect.h };
    this.right = gap ? { x: rect.x + leftWidth + gap, y: rect.y, w: Math.max(0, rect.w - leftWidth - gap), h: rect.h } : { ...EMPTY_RECT };
    this.picker.layout(this.left);
  }

  /** @param {boolean} focused */
  draw(focused) {
    this.picker.draw(focused);
    const right = this.right;
    if (right.w <= 0 || right.h <= 0) return;
    const separator = this.left.x + this.left.w + 1;
    for (let row = 0; row < this.rect.h; row++) text(separator, this.rect.y + row, "│", "UIBorder");
    const selected = this.picker.list.selected();
    let details = "";
    let workspace = "";
    if (!selected) {
      this.title.setText("No matching sessions");
      this.notice.setText("Change the query or press Tab to change scope.");
    } else {
      const session = selected.session;
      this.title.setText(titleOf(session));
      details = this.stateLabel(selected) + " · updated " + ageLabel(session.updated_at_ms) + " · " + session.message_count + (session.message_count === 1 ? " message" : " messages") + " · " + modelLabel(session.model || "no model");
      workspace = session.root;
    }
    const titleHeight = Math.min(2, this.title.measure(right.w).h);
    this.title.layout({ x: right.x, y: right.y, w: right.w, h: titleHeight });
    this.title.draw();
    const metaY = right.y + titleHeight;
    if (metaY < right.y + right.h) text(right.x, metaY, clip(details, right.w), "UIDim");
    if (metaY + 1 < right.y + right.h) text(right.x, metaY + 1, clip(workspace, right.w), "UIDim");
    const body = { x: right.x, y: metaY + 3, w: right.w, h: Math.max(0, right.y + right.h - metaY - 3) };
    if (!selected) {
      this.notice.layout(body);
      this.notice.draw();
      return;
    }
    const preview = this.previews.get(selected.session.id);
    if (preview?.state === "ready") {
      preview.transcript.draw(body);
      return;
    }
    this.notice.setText(preview?.state === "error" ? "Could not load recent messages.\n" + preview.message : "Loading recent messages…");
    this.notice.layout(body);
    this.notice.draw();
  }

  /** @returns {{ x: number, y: number, visible: boolean } | null} */
  cursor() { return this.picker.cursor(); }

  /** @param {Parameters<Window["onKey"]>[0]} event @returns {boolean} */
  onKey(event) {
    if (event.type !== "key") return true;
    const handled = this.picker.onKey(event);
    this.ctx.tui.root.invalidatePaint();
    return handled;
  }

  /** @param {Parameters<Picker<Wire.SessionListItem>["onMouse"]>[0]} event @returns {boolean} */
  onMouse(event) {
    if (event.col >= this.right.x && event.col < this.right.x + this.right.w && event.row >= this.right.y && event.row < this.right.y + this.right.h) {
      const preview = this.readyPreview();
      const handled = preview ? preview.transcript.onMouse(event) : false;
      if (handled) this.ctx.tui.root.invalidatePaint();
      return handled;
    }
    const handled = this.picker.onMouse(event);
    if (handled) this.ctx.tui.root.invalidatePaint();
    return handled;
  }

  /** @returns {{ periodMs: number }} */
  needsTick() { return ONE_SECOND; }

  tick() { this.ctx.tui.root.invalidatePaint(); }
}

/** @param {InjectContext} ctx @param {Wire.SessionListItem[]} items @param {Map<string, "closed" | "here" | "elsewhere">} ownership @param {string | null} workspace @param {string | null} currentId @param {"workspace" | "all"} initialScope */
function showBrowser(ctx, items, ownership, workspace, currentId, initialScope) {
  if (items.length === 0) {
    ctx.interaction.notify("No sessions yet.", "info");
    return;
  }
  // The newest update wins. Creation time and id make equal timestamps stable.
  items.sort((a, b) => b.session.updated_at_ms - a.session.updated_at_ms || b.session.created_at_ms - a.session.created_at_ms || (a.session.id < b.session.id ? -1 : 1));
  /** @type {Map<string, Wire.SessionActivity>} */
  const live = new Map();
  for (let i = 0; i < sessions.length; i++) {
    const session = sessions[i];
    if (session.sessionId && session.activity) live.set(session.sessionId, session.activity);
  }
  const browser = new SessionBrowser(ctx, items, live, ownership, workspace, currentId, initialScope);
  const win = new Window({
    title: () => {
      const shown = browser.picker.list.items.length;
      const total = browser.picker.source.length;
      return "Sessions · " + browser.scopeLabel() + " · " + (shown === total ? total : shown + "/" + total);
    },
    footer: () => browser.footer(),
    border: "rounded",
    width: (max) => Math.round(max * 0.94),
    height: (max) => Math.round(max * 0.86),
    padding: { x: 1, y: 0 },
    content: browser,
  });
  browser.picker.win = win;
  const offActivity = ctx.on("activity.changed", (sessionId, activity) => {
    if (activity) live.set(sessionId, activity);
    else live.delete(sessionId);
    ctx.tui.root.invalidatePaint();
  });
  ctx.tui.overlay(win, () => {
    browser.closed = true;
    offActivity();
  });
}

/** Replace `/sessions` with a themed workspace session browser and add `/resume` as its alias. */
export const sessionsReworked = /** @type {Plugin} */ ({
  name: "sessions-reworked",
  apply(ctx) {
    ctx.inject(["tui"], (c) => {
      c.tui.style.set({
        SessionTitle: { link: "UIItem", fg: "strongFg", bold: true },
        SessionTitleSel: { link: "UIItemSel", fg: "strongFg", bold: true },
        SessionCurrent: { link: "UIItem", fg: "accent", bold: true },
        SessionCurrentSel: { link: "UIItemSel", fg: "accent", bold: true },
        SessionWorking: { link: "UIItem", fg: "warn", bold: true },
        SessionWorkingSel: { link: "UIItemSel", fg: "warn", bold: true },
        SessionElsewhere: { link: "UIItem", fg: "danger", bold: true },
        SessionElsewhereSel: { link: "UIItemSel", fg: "danger", bold: true },
        SessionContext: { link: "UIItem", fg: "fg" },
        SessionContextSel: { link: "UIItemSel", fg: "fg" },
        SessionMeta: { link: "UIDim" },
        SessionMetaSel: { link: "UIDimSel" },
      }, { default: true });
      let loading = false;
      const open = async (arg = "") => {
        if (loading) return;
        const requested = typeof arg === "string" ? arg.trim() : "";
        if (requested && requested !== "all" && requested !== "current" && requested !== "workspace") {
          c.interaction.notify("Usage: /sessions [current | all]", "info");
          return;
        }
        const entry = currentEntry();
        let workspace = entry?.session.root || null;
        const currentId = currentPane()?.session.sessionId || null;
        loading = true;
        try {
          const items = await listSessions();
          const ownership = await sessionOwnership(items);
          if (!workspace && currentId) workspace = items.find((item) => item.session.id === currentId)?.session.root || null;
          if (!workspace) workspace = await launchWorkspace();
          const initialScope = requested === "all" || !workspace ? "all" : "workspace";
          if (c.alive) showBrowser(c, items, ownership, workspace, currentId, initialScope);
        } catch (error) {
          if (c.alive) c.interaction.notify("Cannot list sessions: " + errorText(error), "error");
        } finally {
          loading = false;
        }
      };
      c.tui.command.add("ui:sessions", { desc: "find and resume a session", slash: "sessions", args: true, run: open });
      c.tui.command.add("resume", {
        desc: "alias for /sessions",
        slash: true,
        args: true,
        run: (arg = "") => c.tui.command.perform("ui:sessions", arg),
      });
    });
  },
});
