//! Manifest entry with context-owned registrations and explicit resource lifetimes.
/** @import { UiBorrow } from "../../types.js" */
//! Search saved chats, sessions, and workspace files in a native two-panel finder.
import { client, env, lines, spawn } from "yuke";
import { currentEntry, currentPane } from "yuke:session";
import { Document, Pager, Picker, Window, clip, text } from "yuke:ui";
import { launchWorkspace, listSessions, navigateSession, sessionOwnership } from "../../lib/session-navigation.js";
import { herdrSessionPanes } from "../herdr/index.js";

/** @typedef {"all" | "chats" | "files"} Source */
/** @typedef {{ kind: "session" | "chat" | "file" | "text", key: string, session_id: string, title: string, detail: string, path: string, line: number, message_id: number, part_id: number, row?: { lines: { text: string, group: string, selGroup: string, marker?: string, markerGroup?: string, markerSelGroup?: string, indent?: number }[] } }} Result */
/** @typedef {{ items?: Result[], dirty?: string[], text?: string, note?: string, matches?: string[] }} Reply */

const SOURCES = /** @type {Source[]} */ (["all", "chats", "files"]);

/** @param {unknown} error @returns {string} */
function errorText(error) { return error instanceof Error ? error.message : String(error); }

/** @param {Wire.Session} session @returns {string} */
function signature(session) { return session.updated_at_ms + ":" + session.message_count; }

class SearchWorker {
  /** @param {ReturnType<import("yuke").Context["resources"]>} owner @param {string} helper @param {string} database */
  constructor(owner, helper, database) {
    this.owner = owner;
    this.child = spawn(["python3", "-u", helper, database]);
    this.id = 0;
    this.closed = false;
    this.stderr = "";
    /** @type {Map<number, { resolve: (reply: Reply) => void, reject: (error: Error) => void, timer: number }>} */
    this.pending = new Map();
    this.child.onStdout(lines((line) => {
      try {
        const response = /** @type {{ id: number, result?: Reply, error?: string }} */ (JSON.parse(line));
        const pending = this.pending.get(response.id);
        if (!pending) return;
        clearTimeout(pending.timer);
        this.pending.delete(response.id);
        if (response.error) pending.reject(new Error(response.error));
        else if (response.result) pending.resolve(response.result);
        else pending.reject(new Error("Search helper returned no result."));
      } catch (error) { this.close(new Error(errorText(error))); }
    }, () => this.close(new Error("Search helper output exceeds 1 MiB."))));
    this.child.onStderr((chunk) => { this.stderr = (this.stderr + chunk).slice(-2048); });
    this.child.exited.then(() => this.close(new Error(this.stderr.trim() || "Search helper stopped.")), (error) => this.close(new Error(errorText(error))));
  }

  /** @param {Record<string, unknown>} request @returns {Promise<Reply>} */
  request(request) {
    if (this.closed) return Promise.reject(new Error("Search closed."));
    const id = ++this.id;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => this.close(new Error("Search helper exceeded 30 seconds.")), 30000);
      this.pending.set(id, { resolve, reject, timer });
      this.child.write(JSON.stringify({ ...request, id }) + "\n").catch((error) => this.close(new Error(errorText(error))));
    });
  }

  /** @param {Error} [error] */
  close(error = new Error("Search closed.")) {
    if (this.closed) return;
    this.closed = true;
    this.child.kill();
    this.pending.forEach((pending) => { clearTimeout(pending.timer); pending.reject(error); });
    this.pending.clear();
  }
}

class SearchBrowser {
  /** @param {UiBorrow} ctx @param {SearchWorker} worker @param {string | null} workspace @param {string} query */
  constructor(ctx, worker, workspace, query) {
    this.ctx = ctx;
    this.worker = worker;
    this.workspace = workspace;
    this.scope = workspace ? "workspace" : "all";
    this.source = /** @type {Source} */ ("all");
    this.closed = false;
    this.busy = false;
    this.refreshing = false;
    this.searching = false;
    this.refreshAgain = false;
    this.timer = 0;
    this.refreshTimer = 0;
    this.generation = 0;
    this.previewGeneration = 0;
    this.status = "Reading chats…";
    this.statusGroup = "SearchPending";
    this.note = "";
    this.heading = "Search";
    this.footer = "";
    this.previewKey = "";
    this.previewReady = false;
    this.previewText = "Choose a result to preview it.\n\nTab: workspace/all sessions\nCtrl+T: source\nCtrl+R: refresh\nCtrl+Y: insert excerpt or path";
    this.previewNote = "";
    this.previewWidth = -1;
    this.pattern = /** @type {RegExp | null} */ (null);
    this.document = new Document();
    this.document.setText(this.previewText);
    this.pager = new Pager();
    this.rect = { x: 0, y: 0, w: 0, h: 0 };
    this.left = { x: 0, y: 0, w: 0, h: 0 };
    this.right = { x: 0, y: 0, w: 0, h: 0 };
    this.body = { x: 0, y: 0, w: 0, h: 0 };
    /** @type {Result[]} */
    this.results = [];
    /** @type {Map<string, Wire.SessionListItem>} */
    this.sessions = new Map();
    /** @type {Map<string, "closed" | "here" | "elsewhere">} */
    this.owners = new Map();
    /** @type {Map<string, string>} */
    this.herdrPanes = new Map();
    this.picker = new Picker({
      items: this.results, suggest: () => this.results, key: (item) => item.key,
      itemHeight: 2, format: (item) => item.row || item.title,
      onMove: () => this.loadPreview(), closeOnAccept: false,
      onAccept: (item) => { void this.accept(item); },
      keymap: {
        tab: () => { this.scope = this.scope === "workspace" ? "all" : this.workspace ? "workspace" : "all"; this.schedule(true); },
        "ctrl+t": () => { this.source = SOURCES[(SOURCES.indexOf(this.source) + 1) % SOURCES.length]; this.schedule(true); },
        "ctrl+r": () => { void this.refresh(); },
        "ctrl+y": () => this.insert(),
        "ctrl+d": () => { this.pager.navPage(1); ctx.tui.root.invalidatePaint(); },
        "ctrl+u": () => { this.pager.navPage(-1); ctx.tui.root.invalidatePaint(); },
      },
    });
    if (this.picker.input) this.picker.input.onChange = () => this.schedule(true);
    this.picker.query = query;
    this.updateLabels();
  }

  updateLabels() {
    this.heading = "Search · " + this.scope + " · " + this.source + " · " + this.results.length;
    this.footer = "tab scope · ctrl+t all/chats/files · enter open · ctrl+y insert · ctrl+d/u scroll · ctrl+r refresh";
    this.ctx.tui.root.invalidate();
  }

  /** @param {boolean} [clear] */
  schedule(clear = false) {
    if (this.closed) return;
    this.generation++;
    if (clear) {
      this.results = [];
      this.picker.setSource(this.results);
      this.loadPreview();
      this.note = "Searching…";
    }
    clearTimeout(this.timer);
    this.timer = setTimeout(() => { this.timer = 0; void this.search(); }, 120);
    this.updateLabels();
  }

  async search() {
    if (this.closed || this.searching) return;
    this.searching = true;
    const generation = this.generation;
    try {
      const reply = await this.worker.request({ action: "search", query: this.picker.query, source: this.source, root: this.scope === "workspace" ? this.workspace : null });
      if (this.closed || generation !== this.generation) return;
      this.results = reply.items || [];
      this.note = reply.note || (this.results.length ? "" : "No matches. Try fewer words, another source, or all sessions.");
      for (let i = 0; i < this.results.length; i++) {
        const item = this.results[i];
        const owner = this.owners.get(item.session_id);
        const state = owner === "elsewhere" ? this.herdrPanes.has(item.session_id) ? " · jump to Herdr" : " · open elsewhere" : owner === "here" ? " · open here" : "";
        const group = item.kind === "chat" ? "SearchChat" : item.kind === "session" ? "SearchSession" : "SearchFile";
        const badge = item.kind.toUpperCase();
        item.row = { lines: [
          { marker: badge, markerGroup: group, markerSelGroup: group + "Sel", indent: badge.length + 2, text: item.title + state, group: "SearchTitle", selGroup: "SearchTitleSel" },
          { text: item.detail.replace(/\s+/gu, " "), group: "SearchDetail", selGroup: "SearchDetailSel" },
        ] };
      }
      const selectedKey = this.picker.list.selected()?.key;
      this.picker.setSource(this.results);
      if (selectedKey) this.picker.list.selectKey(selectedKey);
      this.loadPreview();
      this.updateLabels();
    } catch (error) {
      if (!this.closed && generation === this.generation) {
        this.note = "Search failed: " + errorText(error);
        this.updateLabels();
      }
    } finally {
      this.searching = false;
      if (!this.closed && generation !== this.generation && !this.timer) void this.search();
    }
  }

  async refresh() {
    if (this.closed) return;
    if (this.refreshing) { this.refreshAgain = true; return; }
    this.refreshing = true;
    this.status = "Reading chats…";
    this.statusGroup = "SearchPending";
    this.updateLabels();
    try {
      const items = await listSessions();
      if (this.closed) return;
      this.sessions = new Map(items.map((item) => [item.session.id, item]));
      this.owners = await sessionOwnership(items, this.worker.owner.signal);
      this.herdrPanes = await herdrSessionPanes(this.worker.owner.signal).catch((error) => {
        this.ctx.ctx.print("Search cannot inspect Herdr panes", errorText(error));
        return new Map();
      });
      if (this.closed) return;
      const manifest = items.map(({ session }) => ({ id: session.id, title: session.title.trim() || session.name?.trim() || "Untitled session", root: session.root, signature: signature(session), updated: session.updated_at_ms }));
      const reply = await this.worker.request({ action: "manifest", items: manifest });
      const dirty = new Set(reply.dirty || []);
      this.previewKey = "";
      this.schedule(true);
      items.sort((a, b) => Number(b.session.root === this.workspace) - Number(a.session.root === this.workspace) || b.session.updated_at_ms - a.session.updated_at_ms);
      let done = 0;
      let failed = 0;
      let updating = 0;
      let failure = "";
      for (let i = 0; i < items.length; i++) {
        const item = items[i];
        if (this.closed) return;
        if (!dirty.has(item.session.id)) continue;
        this.status = "Indexing saved chats " + done + "/" + dirty.size;
        this.updateLabels();
        try {
          const changed = await this.indexSession(item.session);
          if (changed && await this.indexSession(changed)) updating++;
        }
        catch (error) {
          if (this.closed) return;
          failed++;
          if (!failure) failure = errorText(error);
          this.ctx.ctx.print("Search could not index session", item.session.id, errorText(error));
        }
        done++;
        if (!this.timer) this.schedule();
      }
      this.status = failed ? failed + " failed: " + failure : updating ? updating + " chats updating · saved text will refresh" : "Saved chat index ready";
      this.statusGroup = failed ? "SearchError" : updating ? "SearchPending" : "SearchReady";
      this.schedule();
    } catch (error) {
      if (!this.closed) { this.status = "Index failed: " + errorText(error); this.statusGroup = "SearchError"; this.updateLabels(); }
    } finally {
      this.refreshing = false;
      if (this.refreshAgain && !this.closed) { this.refreshAgain = false; void this.refresh(); }
    }
  }

  /** @param {Wire.Session} session @returns {Promise<Wire.Session | null>} */
  async indexSession(session) {
    await this.worker.request({ action: "begin", session_id: session.id });
    let before = 0;
    const cursors = new Set();
    for (let pageIndex = 0; pageIndex < 1000; pageIndex++) {
      if (this.closed) return null;
      const page = await client.request("session.history", { session_id: session.id, before_message_id: before, limit: 20 });
      if (this.closed) return null;
      for (let i = 0; i < page.messages.length; i++) {
        const message = page.messages[i];
        if (message.type !== "user" && message.type !== "assistant") continue;
        for (let j = 0; j < message.content.length; j++) {
          const part = message.content[j];
          if (part.type !== "text" || !part.text) continue;
          for (let offset = 0; offset < part.text.length;) {
            if (this.closed) return null;
            let end = Math.min(part.text.length, offset + 32000);
            const last = part.text.charCodeAt(end - 1);
            if (end < part.text.length && last >= 0xd800 && last <= 0xdbff) end--;
            await this.worker.request({ action: "part", session_id: session.id, message_id: message.id, part_id: j, role: message.type, body: part.text.slice(offset, end) });
            offset = end;
          }
        }
      }
      if (!page.has_more) {
        const latest = await client.sessionGet(session.id);
        if (this.closed) return null;
        if (signature(latest.session) !== signature(session)) {
          const next = latest.session;
          this.sessions.set(next.id, latest);
          await this.worker.request({ action: "manifest", partial: true, items: [{ id: next.id, title: next.title.trim() || next.name?.trim() || "Untitled session", root: next.root, signature: signature(next), updated: next.updated_at_ms }] });
          return next;
        }
        await this.worker.request({ action: "finish", session_id: session.id, signature: signature(session) });
        return null;
      }
      const next = page.messages[0]?.id;
      if (next == null || cursors.has(next)) throw new Error("Session history cursor did not advance.");
      cursors.add(next);
      before = next;
    }
    throw new Error("Session history exceeds 1000 pages.");
  }

  loadPreview() {
    const selected = this.picker.list.selected();
    const key = selected?.key || "";
    if (key === this.previewKey) return;
    this.previewKey = key;
    const generation = ++this.previewGeneration;
    this.previewNote = "";
    this.previewReady = false;
    this.setPreview(selected ? "Loading preview…" : "No matching results.\n\nTry fewer words, Ctrl+T for another source, or Tab for all sessions.");
    if (!selected) return;
    this.worker.request({ action: "preview", item: selected, root: this.workspace, query: this.picker.query }).then((reply) => {
      if (this.closed || generation !== this.previewGeneration) return;
      this.previewNote = reply.note || "";
      this.previewReady = true;
      this.setPreview(reply.text || "No text to preview.", reply.matches);
    }, (error) => {
      if (!this.closed && generation === this.previewGeneration) this.setPreview("Preview failed: " + errorText(error));
    });
  }

  /** @param {string} value @param {string[]} [matches] */
  setPreview(value, matches) {
    this.previewText = value;
    const words = matches || this.picker.query.match(/[\p{L}\p{N}_]+/gu);
    this.pattern = words?.length ? new RegExp(words.map((word) => word.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|"), "giu") : null;
    const selected = this.picker.list.selected();
    this.document.setText(selected?.kind === "file" || selected?.kind === "text" ? "    " + value.replace(/\n/g, "\n    ") : value);
    this.previewWidth = -1;
    this.pager.toTop();
    this.ctx.tui.root.invalidate();
  }

  /** @param {Result} item */
  async accept(item) {
    if (this.busy || this.closed) return;
    if (item.kind === "file" || item.kind === "text") { this.insert(); return; }
    const session = this.sessions.get(item.session_id);
    if (!session) { this.ctx.ctx.interaction.notify("That session is gone. Refresh the search.", "warn"); return; }
    this.busy = true;
    try {
      await navigateSession(session, this.worker.owner);
      if (!this.closed) this.picker.close();
    } catch (error) {
      if (!this.closed) this.ctx.ctx.interaction.notify("Cannot open session: " + errorText(error), "warn");
    } finally { this.busy = false; }
  }

  insert() {
    const item = this.picker.list.selected();
    const input = currentPane()?.composer?.input;
    if (!item || !input || this.closed) return;
    if ((item.kind === "chat" || item.kind === "session") && (this.previewKey !== item.key || !this.previewReady)) return;
    const value = item.kind === "file" || item.kind === "text"
      ? JSON.stringify((this.workspace || "") + "/" + item.path) + (item.kind === "text" ? ":" + item.line : "")
      : "From " + JSON.stringify(item.title) + " (session " + item.session_id + (item.kind === "chat" ? ", message " + item.message_id : "") + "):\n> " + this.previewText.slice(0, 8000).replace(/\n/g, "\n> ");
    input.insert((input.beforeCaret() && !/\s$/.test(input.beforeCaret()) ? "\n" : "") + value);
    this.picker.close();
  }

  /** @param {import("yuke:ui").Rect} rect */
  layout(rect) {
    this.rect = rect;
    const gap = rect.w >= 72 ? 3 : 0;
    const leftWidth = gap ? Math.floor((rect.w - gap) * 0.5) : rect.w;
    this.left.x = rect.x;
    this.left.y = rect.y;
    this.left.w = leftWidth;
    this.left.h = rect.h;
    this.right.x = rect.x + leftWidth + gap;
    this.right.y = rect.y;
    this.right.w = gap ? rect.w - leftWidth - gap : 0;
    this.right.h = rect.h;
    this.body.x = this.right.x;
    this.body.y = rect.y + 4;
    this.body.w = this.right.w;
    this.body.h = Math.max(0, rect.h - 4);
    this.picker.layout(this.left);
    if (this.right.w > 0 && this.body.h > 0 && this.previewWidth !== this.right.w) {
      this.pager.setRows(this.previewRows(this.right.w));
      this.previewWidth = this.right.w;
    }
  }

  /** @param {number} width @returns {ReturnType<Document["rows"]>} */
  previewRows(width) {
    const rows = this.document.rows(width);
    const pattern = this.pattern;
    if (!pattern) return rows;
    const marked = [];
    for (let i = 0; i < rows.length; i++) {
      const segments = [];
      const source = rows[i].segments;
      for (let j = 0; j < source.length; j++) {
        const segment = source[j];
        pattern.lastIndex = 0;
        let start = 0;
        let hit;
        while ((hit = pattern.exec(segment.text))) {
          if (hit.index > start) segments.push({ text: segment.text.slice(start, hit.index), group: segment.group });
          segments.push({ text: hit[0], group: "SearchMatch" });
          start = hit.index + hit[0].length;
        }
        if (!start) segments.push(segment);
        else if (start < segment.text.length) segments.push({ text: segment.text.slice(start), group: segment.group });
      }
      marked.push({ segments });
    }
    return marked;
  }

  /** @param {boolean} focused */
  draw(focused) {
    this.picker.draw(focused);
    if (this.right.w <= 0 || this.right.h <= 0) return;
    for (let row = 0; row < this.rect.h; row++) text(this.left.x + this.left.w + 1, this.rect.y + row, "│", "UIBorder");
    const selected = this.picker.list.selected();
    text(this.right.x, this.right.y, clip(selected?.title || "Search", this.right.w), "SearchTitle");
    if (this.right.h > 1) text(this.right.x, this.right.y + 1, clip(this.status, this.right.w), this.statusGroup);
    if (this.right.h > 2) text(this.right.x, this.right.y + 2, clip(this.note || this.previewNote, this.right.w), "UIDim");
    this.pager.draw(this.body);
  }

  cursor() { return this.picker.cursor(); }

  /** @param {Parameters<Window["onKey"]>[0]} event */
  onKey(event) { return event.type === "key" ? this.picker.onKey(event) : true; }

  /** @param {Parameters<Pager["onMouse"]>[0]} event */
  onMouse(event) {
    if (event.col >= this.right.x && this.right.w > 0) {
      const handled = this.pager.onMouse(event);
      if (handled) this.ctx.tui.root.invalidatePaint();
      return handled;
    }
    return this.picker.onMouse(event);
  }

  close() {
    this.closed = true;
    clearTimeout(this.timer);
    clearTimeout(this.refreshTimer);
    this.worker.close();
  }
}
/** Register the migrated search operations. The plugin owns registrations; host failures throw. @param {import("yuke").Context} parent */
export default function(parent) {

    {
const tuiBorrow = parent.get("tui");
if (tuiBorrow) {
const c = { ctx: parent, tui: tuiBorrow };

      c.tui.style.set({
        SearchChat: { link: "UIItem", fg: "cyan", bold: true },
        SearchChatSel: { link: "UIItemSel", fg: "cyan", bold: true },
        SearchFile: { link: "UIItem", fg: "green", bold: true },
        SearchFileSel: { link: "UIItemSel", fg: "green", bold: true },
        SearchSession: { link: "UIItem", fg: c.tui.style.palette.violet != null ? "violet" : "accent", bold: true },
        SearchSessionSel: { link: "UIItemSel", fg: c.tui.style.palette.violet != null ? "violet" : "accent", bold: true },
        SearchMatch: { fg: "warn", bold: true, underline: true },
        SearchPending: { fg: "warn" },
        SearchReady: { fg: "green" },
        SearchError: { fg: "danger", bold: true },
        SearchTitle: { link: "UIItem", fg: "strongFg", bold: true },
        SearchTitleSel: { link: "UIItemSel", bold: true },
        SearchDetail: { link: "UIDim" },
        SearchDetailSel: { link: "UIItemSel" },
      }, { default: true });
      /** @type {SearchBrowser | null} */
      let browser = null;
      let opening = false;
      let released = Promise.resolve();
      const home = env.get("HOME") || ".";
      const app = env.get("YUKE_APPNAME") || "yuke";
      const helper = (env.get("XDG_CONFIG_HOME") || home + "/.config") + "/" + app + "/plugins/search-store.py";
      const database = (env.get("XDG_CACHE_HOME") || home + "/.cache") + "/" + app + "/search/history-v1.db";
      c.ctx.on("index.changed", () => {
        if (!browser || browser.closed) return;
        clearTimeout(browser.refreshTimer);
        browser.refreshTimer = setTimeout(() => { if (browser) void browser.refresh(); }, 500);
      });
      c.ctx.on("message.committed", () => {
        if (!browser || browser.closed) return;
        clearTimeout(browser.refreshTimer);
        browser.refreshTimer = setTimeout(() => { if (browser) void browser.refresh(); }, 500);
      });
      c.tui.command.add("open", {
        desc: "search sessions, saved chats, and workspace files", slash: "search", args: true,
        run: async (query = "") => {
          if (browser || opening) return;
          opening = true;
          try {
            await released;
            if (!c.ctx.alive) return;
            const workspace = currentEntry()?.session.root || await launchWorkspace();
            if (!c.ctx.alive) return;
            const owner = c.ctx.resources("search-dialog");
            try {
              const worker = new SearchWorker(owner, helper, database);
              const view = new SearchBrowser(c, worker, workspace, typeof query === "string" ? query : "");
              browser = view;
              const win = new Window({
                name: "search", title: () => view.heading, footer: () => view.footer, border: "rounded",
                width: (max) => Math.round(max * 0.94), height: (max) => Math.round(max * 0.86),
                padding: { x: 1, y: 0 }, content: view,
              });
              view.picker.win = win;
              owner.own(() => {
                view.close();
                c.tui.root.popOverlay(win);
                if (browser === view) browser = null;
                return worker.child.exited.then(() => {}, () => {});
              });
              c.tui.overlay(win, () => {
                view.close();
                if (browser === view) browser = null;
                released = Promise.resolve(owner.dispose());
              });
              void view.refresh();
            } catch (error) { await owner.dispose(); throw error; }
          } catch (error) { if (c.ctx.alive) c.ctx.interaction.notify("Cannot open search: " + errorText(error), "error"); }
          finally { opening = false; }
        },
      });
}
}
  
}
