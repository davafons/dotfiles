/** @import { UiBorrow } from "../../types.js" */
//! Full-screen project work. Layout and state changes build the paint cache; draw only paints it.
import { clip, fill, keys, measure, text, Window } from "yuke:ui";
import { wrapRows } from "yuke:chat";

/** @import { Rect } from "yuke:ui" */
/** @import { Observation } from "./activity.js" */
/** @import { GitHubItem, GitHubPage, GitHubDetail } from "./project-work-github.js" */
/** @typedef {{ id: string, title: string, status: string, notes: string, session: string, root: string, updated: number, version: number, github_url: string }} Task */
/** @typedef {{ session: string, task_id: string, summary: string, next_step: string, verification: string, root: string, updated: number, stale: number }} Checkpoint */
/** @typedef {{ project: string, name: string, root: string, context: { goal: string, notes: string, version: number }, tasks: Task[], counts: number[], offsets: number[], query: string, include_done: boolean, checkpoints: Checkpoint[] }} BoardSnapshot */
/** @typedef {{ activityRead?: (ids: string[]) => Promise<Map<string, Observation>>, read: (offsets: number[], query: string, done: boolean) => Promise<BoardSnapshot>, detail: (id: string) => Promise<{task: Task, checkpoint: Checkpoint | null}>, githubRead: (args: Record<string, unknown>) => Promise<GitHubPage>, githubDetail: (args: Record<string, unknown>) => Promise<GitHubDetail>, action: (name: string, task: Task | null, checkpoint: Checkpoint | null) => Promise<"close" | void> }} Actions */
/** @typedef {{x: number, y: number, value: string, group: string}} Span */
/** @typedef {{x: number, y: number, w: number, h: number, group: string}} Block */
/** @typedef {{x: number, y: number, w: number, h: number, kind: string, column: number, index: number, action: string}} Hit */
/** @typedef {{value: string, group: string}} Line */

const STAGES = ["Now", "Later", "Blocked", "Review", "Done"];
const STATUS = ["now", "later", "blocked", "review", "done"];
const GROUPS = ["WorkNow", "WorkLater", "WorkBlocked", "WorkReview", "WorkDone"];
const SELECTED = ["WorkSelectedNow", "WorkSelectedLater", "WorkSelectedBlocked", "WorkSelectedReview", "WorkSelectedDone"];
const TABS = ["Board", "Context", "Checkpoints", "GitHub"];
const ACTIVE_FIRST = [0, 2, 3, 1, 4];
const FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧"];

/** The full-screen work view owns its snapshots, selection, and paint cache. It borrows its plugin context and actions. Null data means loading; failed actions show an error without changing the composer. */
export class WorkDashboard {
  /** @param {UiBorrow} ctx @param {Actions} actions */
  constructor(ctx, actions) {
    this.ctx = ctx;
    this.actions = actions;
    this.rect = { x: 0, y: 0, w: 0, h: 0 };
    this.detailRect = { x: 0, y: 0, w: 0, h: 0 };
    this.tab = 0;
    this.column = 0;
    this.selected = 0;
    this.checkpointIndex = 0;
    this.detailScroll = 0;
    this.scrolls = [0, 0, 0, 0, 0];
    this.offsets = [0, 0, 0, 0, 0];
    this.query = "";
    this.includeDone = false;
    this.loading = false;
    this.pending = false;
    this.closed = false;
    this.error = "";
    this.githubKind = "issues";
    this.githubState = "open";
    this.githubIndex = 0;
    this.githubPage = 0;
    this.githubCursors = [""];
    this.githubLoading = false;
    this.githubDetailLoading = false;
    this.githubGeneration = 0;
    this.githubDetailGeneration = 0;
    /** @type {GitHubPage | null} */
    this.githubData = null;
    /** @type {GitHubDetail | null} */
    this.githubDetail = null;
    this.generation = 0;
    this.detailGeneration = 0;
    this.close = () => {};
    this.footer = "Esc: return to chat";
    /** @type {BoardSnapshot | null} */
    this.data = null;
    /** @type {Task[][]} */
    this.columns = [[], [], [], [], []];
    /** @type {{task: Task, checkpoint: Checkpoint | null} | null} */
    this.detail = null;
    /** @type {Span[]} */
    this.spans = [];
    /** @type {Block[]} */
    this.blocks = [];
    /** @type {Hit[]} */
    this.hits = [];
    /** @type {Map<string, Observation>} */
    this.activity = new Map();
    this.activityPending = false;
    this.frame = 0;
    /** @type {{spanBorrow: Span, framesOwn: string[]}[]} */
    this.animatedSpans = [];
  }

  /** Resolve the latest known task checkpoint without changing its recorded owner. @param {Task} task @returns {string} */
  linkedSession(task) {
    if (this.detail?.task.id === task.id && this.detail.checkpoint?.session) return this.detail.checkpoint.session;
    const checkpoints = this.data?.checkpoints || [];
    for (let i = 0; i < checkpoints.length; i++) if (checkpoints[i].task_id === task.id) return checkpoints[i].session;
    return task.session;
  }

  /** Read a bounded live snapshot outside drawing. Closed or replaced boards reject late results. */
  async refreshActivity() {
    const data = this.data;
    if (this.closed || this.activityPending || !data || !this.actions.activityRead) return;
    this.activityPending = true;
    try {
      const ids = data.tasks.map(task => this.linkedSession(task));
      const observed = await this.actions.activityRead(ids);
      if (this.closed || this.data !== data) return;
      let changed = observed.size !== this.activity.size;
      observed.forEach((value, id) => { const previous = this.activity.get(id); if (!previous || previous.label !== value.label || previous.running !== value.running) changed = true; });
      if (changed) { this.activity = observed; this.rebuild(); }
    } catch {
      if (!this.closed && this.data === data && this.activity.size) { this.activity.clear(); this.rebuild(); }
    } finally { this.activityPending = false; }
  }

  /** Advance prebuilt marker text. This mutates no task and allocates no rows or strings. */
  animate() {
    if (this.closed || !this.animatedSpans.length) return;
    this.frame = (this.frame + 1) & 7;
    for (let i = 0; i < this.animatedSpans.length; i++) {
      const held = this.animatedSpans[i];
      held.spanBorrow.value = held.framesOwn[this.frame] || "";
    }
    this.ctx.tui.root.invalidatePaint();
  }

  /** @returns {Task | null} */
  selectedTask() { return this.columns[this.column]?.[this.selected] || null; }

  /** @returns {GitHubItem | null} */
  selectedGitHubItem() { return this.githubData?.items[this.githubIndex] || null; }

  async refreshGitHub() {
    if (this.githubLoading || this.closed) return;
    const generation = ++this.githubGeneration;
    this.githubLoading = true;
    this.error = "";
    this.rebuild();
    try {
      const data = await this.actions.githubRead({ action: "list", kind: this.githubKind, state: this.githubState, cursor: this.githubCursors[this.githubPage] });
      if (this.closed || generation !== this.githubGeneration) return;
      this.githubData = data;
      this.githubIndex = Math.max(0, Math.min(this.githubIndex, data.items.length - 1));
      this.detailScroll = 0;
      this.loadGitHubDetail();
    } catch (error) {
      if (!this.closed && generation === this.githubGeneration) this.error = String(error);
    } finally {
      if (!this.closed && generation === this.githubGeneration) { this.githubLoading = false; this.rebuild(); }
    }
  }

  loadGitHubDetail() {
    this.githubDetailGeneration++;
    this.githubDetail = null;
    if (!this.githubDetailLoading) this.readGitHubDetail();
  }

  readGitHubDetail() {
    const item = this.selectedGitHubItem();
    if (!item || this.closed) return;
    const generation = this.githubDetailGeneration;
    this.githubDetailLoading = true;
    void this.actions.githubDetail({ action: "get", kind: this.githubKind, number: item.number, repo: this.githubData?.repo }).then((detail) => {
      if (this.closed || generation !== this.githubDetailGeneration) return;
      this.githubDetail = detail;
    }).catch((error) => {
      if (!this.closed && generation === this.githubDetailGeneration) this.error = String(error);
    }).finally(() => {
      this.githubDetailLoading = false;
      if (this.closed) return;
      if (generation !== this.githubDetailGeneration) this.readGitHubDetail();
      this.rebuild();
    });
  }

  /** @param {number} delta */
  pageGitHub(delta) {
    if (this.githubLoading || this.pending || !this.githubData) return;
    if (delta > 0) {
      if (!this.githubData.has_next) return;
      this.githubCursors[this.githubPage + 1] = this.githubData.next_cursor;
    } else if (!this.githubPage) return;
    this.githubPage += delta;
    this.githubIndex = 0;
    void this.refreshGitHub();
  }

  async refresh() {
    if (this.loading || this.closed) return;
    const generation = ++this.generation;
    const selectedId = this.selectedTask()?.id;
    this.loading = true;
    this.error = "";
    this.rebuild();
    try {
      const data = await this.actions.read(this.offsets, this.query, this.includeDone);
      if (this.closed || generation !== this.generation) return;
      this.data = data;
      this.columns = STATUS.map((status) => data.tasks.filter((task) => task.status === status));
      let found = false;
      for (let column = 0; column < this.columns.length; column++) {
        const index = this.columns[column].findIndex((task) => task.id === selectedId);
        if (index >= 0) { this.column = column; this.selected = index; found = true; break; }
      }
      if (!found) {
        if (!this.columns[this.column].length) this.column = ACTIVE_FIRST.find((column) => this.columns[column].length > 0) ?? 0;
        this.selected = 0;
      }
      this.checkpointIndex = Math.max(0, Math.min(this.checkpointIndex, data.checkpoints.length - 1));
      this.detailScroll = 0;
      this.detail = null;
      this.loadDetail();
      void this.refreshActivity();
    } catch (error) {
      if (!this.closed && generation === this.generation) this.error = String(error);
    } finally {
      if (!this.closed && generation === this.generation) { this.loading = false; this.rebuild(); }
    }
  }

  loadDetail() {
    const task = this.selectedTask();
    const generation = ++this.detailGeneration;
    this.detail = null;
    if (!task || this.closed) return;
    void this.actions.detail(task.id).then((detail) => {
      if (this.closed || generation !== this.detailGeneration || this.selectedTask()?.id !== detail.task.id) return;
      this.detail = detail;
      this.rebuild();
    }).catch((error) => {
      if (!this.closed && generation === this.detailGeneration) { this.error = String(error); this.rebuild(); }
    });
  }

  /** @param {string} name */
  async act(name) {
    if (this.pending || this.loading || this.githubLoading || this.closed) return;
    this.pending = true;
    this.error = "";
    this.rebuild();
    try {
      if (name === "github_kind" || name === "github_state") {
        if (name === "github_kind") this.githubKind = this.githubKind === "issues" ? "pulls" : "issues";
        else this.githubState = this.githubState === "open" ? "closed" : this.githubState === "closed" ? "all" : "open";
        this.githubPage = this.githubIndex = 0;
        this.githubCursors = [""];
        this.githubData = null;
        this.githubDetail = null;
        await this.refreshGitHub();
        return;
      }
      if (name === "search") {
        const query = await this.ctx.ctx.interaction.input("Filter project tasks", "Title or notes; blank clears the filter");
        if (query == null || this.closed) return;
        this.query = query;
        this.offsets = [0, 0, 0, 0, 0];
      } else if (name === "done") {
        this.includeDone = !this.includeDone;
        this.offsets[4] = 0;
      } else {
        const checkpoint = this.tab === 2 ? this.data?.checkpoints[this.checkpointIndex] || null : null;
        if (await this.actions.action(name, this.tab === 0 ? this.selectedTask() : null, checkpoint) === "close") {
          this.close();
          return;
        }
      }
      if (!this.closed) {
        await this.refresh();
        if (this.tab === 3) this.loadGitHubDetail();
      }
    } catch (error) {
      if (!this.closed) this.error = String(error);
    } finally {
      this.pending = false;
      if (!this.closed) this.rebuild();
    }
  }

  /** @param {number} tab */
  selectTab(tab) {
    this.tab = (tab + TABS.length) % TABS.length;
    this.detailScroll = 0;
    if (this.tab === 3 && !this.githubData) void this.refreshGitHub();
    this.rebuild();
  }

  /** @param {number} delta */
  moveColumn(delta) {
    this.column = (this.column + delta + STAGES.length) % STAGES.length;
    this.selected = Math.min(this.selected, Math.max(0, this.columns[this.column].length - 1));
    this.detailScroll = 0;
    this.loadDetail();
    this.rebuild();
  }

  /** @param {number} delta */
  move(delta) {
    if (this.tab === 3) {
      const next = Math.max(0, Math.min(this.githubIndex + delta, (this.githubData?.items.length || 0) - 1));
      if (next === this.githubIndex) return;
      this.githubIndex = next;
      this.detailScroll = 0;
      this.loadGitHubDetail();
    } else if (this.tab === 0) {
      this.selected = Math.max(0, Math.min(this.selected + delta, this.columns[this.column].length - 1));
      this.detailScroll = 0;
      this.loadDetail();
    } else if (this.tab === 2) {
      this.checkpointIndex = Math.max(0, Math.min(this.checkpointIndex + delta, (this.data?.checkpoints.length || 0) - 1));
      this.detailScroll = 0;
    } else this.detailScroll = Math.max(0, this.detailScroll + delta);
    this.rebuild();
  }

  /** @param {number} delta */
  page(delta) {
    if (this.loading || this.pending || !this.data) return;
    const next = Math.max(0, this.offsets[this.column] + delta * 5);
    if (next >= this.data.counts[this.column] && next > 0) return;
    this.offsets[this.column] = next;
    this.scrolls[this.column] = 0;
    void this.refresh();
  }

  /** @param {Rect} rect */
  layout(rect) {
    if (this.rect.x === rect.x && this.rect.y === rect.y && this.rect.w === rect.w && this.rect.h === rect.h) return;
    this.rect = rect;
    this.rebuild();
  }

  draw() {
    const rect = this.rect;
    const blocks = this.blocks;
    for (let i = 0; i < blocks.length; i++) {
      const block = blocks[i];
      fill(rect.x + block.x, rect.y + block.y, block.w, block.h, block.group);
    }
    const spans = this.spans;
    for (let i = 0; i < spans.length; i++) {
      const span = spans[i];
      text(rect.x + span.x, rect.y + span.y, span.value, span.group);
    }
  }

  /** @param {number} x @param {number} y @param {string} value @param {number} width @param {string} group */
  put(x, y, value, width, group) {
    if (y < 0 || y >= this.rect.h || x < 0 || x >= this.rect.w || width <= 0) return;
    this.spans.push({ x, y, value: clip(value, Math.min(width, this.rect.w - x)), group });
  }

  /** @param {Rect} rect @param {Line[]} lines */
  paintDetails(rect, lines) {
    this.detailRect = rect;
    const scrollable = lines.length > rect.h;
    const visible = Math.max(0, rect.h - (scrollable ? 1 : 0));
    this.detailScroll = Math.max(0, Math.min(this.detailScroll, lines.length - visible));
    for (let i = 0; i < visible; i++) {
      const row = lines[this.detailScroll + i];
      if (!row) break;
      this.put(rect.x, rect.y + i, row.value, rect.w, row.group);
    }
    if (lines.length > rect.h) this.put(rect.x, rect.y + rect.h - 1, "PageUp/PageDown: more details", rect.w, "WorkShortcut");
  }

  /** @param {Line[]} rows @param {string} label @param {string} value @param {number} width @param {string} group */
  paragraph(rows, label, value, width, group) {
    rows.push({ value: label, group: "WorkDim" });
    const wrapped = wrapRows(value || "Not recorded", Math.max(1, width), group, 0, 300);
    for (let i = 0; i < wrapped.length; i++) {
      const row = wrapped[i];
      rows.push({ value: row.text || row.segments?.map((segment) => segment.text).join("") || "", group });
    }
    rows.push({ value: "", group: "WorkText" });
  }

  /** @param {Line[]} rows @param {Checkpoint | null | undefined} checkpoint @param {number} width */
  checkpointRows(rows, checkpoint, width) {
    if (!checkpoint) { rows.push({ value: "No checkpoint saved.", group: "WorkDim" }); return; }
    if (checkpoint.stale) this.paragraph(rows, "STALE", "A later run started. Check the source conversation before continuing.", width, "WorkBlocked");
    this.paragraph(rows, "WHERE YOU STOPPED", checkpoint.summary, width, "WorkText");
    this.paragraph(rows, "NEXT STEP", checkpoint.next_step, width, "WorkLater");
    this.paragraph(rows, "VERIFICATION", checkpoint.verification, width, "WorkReview");
    this.paragraph(rows, "CHECKOUT", checkpoint.root, width, "WorkDim");
    this.paragraph(rows, "SESSION", checkpoint.session, width, "WorkDim");
  }

  rebuild() {
    if (this.closed) return;
    this.spans = [];
    this.blocks = [];
    this.hits = [];
    this.animatedSpans.length = 0;
    const width = this.rect.w;
    const height = this.rect.h;
    if (!width || !height) return;
    const data = this.data;
    this.put(0, 0, "Work · " + (data?.name || "project") + (this.loading || this.pending || this.githubLoading ? " · working" : ""), width, "WorkTitle");
    let x = 0;
    for (let i = 0; i < TABS.length; i++) {
      const label = " " + (i + 1) + " " + TABS[i] + " ";
      const w = Math.min(measure(label), Math.max(0, width - x));
      this.put(x, 1, label, w, this.tab === i ? "WorkActiveTab" : "WorkDim");
      this.hits.push({ x, y: 1, w, h: 1, kind: "tab", column: 0, index: i, action: "" });
      x += w + 1;
    }
    this.put(0, 2, "─".repeat(width), width, "WorkRule");
    this.put(0, 3, "Goal: " + (data?.context.goal || "No project goal saved"), width, "WorkText");
    const controls = this.tab === 3 ? [["v " + (this.githubKind === "issues" ? "Issues" : "PRs"), "github_kind"], ["o " + this.githubState, "github_state"], ["a Internal step", "github_add"], ["r Refresh", "github_refresh"]] : [["a Add", "add"], ["m Status", "status"], ["c Checkpoint", "checkpoint"], ["g Goal", "context"], ["/ Filter", "search"], ["d " + (this.includeDone ? "Hide done" : "Show done"), "done"], ["r Refresh", "refresh"]];
    x = 0;
    for (let i = 0; i < controls.length; i++) {
      const label = controls[i][0];
      const w = Math.min(measure(label), Math.max(0, width - x));
      this.put(x, 4, label, w, "WorkShortcut");
      this.hits.push({ x, y: 4, w, h: 1, kind: "control", column: 0, index: 0, action: controls[i][1] });
      x += w + 3;
    }
    if (this.error) this.put(0, 5, this.error, width, "WorkDanger");
    else if (this.query) this.put(0, 5, "Filter: " + this.query, width, "WorkLater");
    else this.put(0, 5, data?.root || "Reading project work…", width, "WorkDim");
    this.footer = width < 90 ? "1-4 tabs · h/l columns · j/k cards · Enter actions · q close" : "1-4/Tab views · h/l columns · j/k cards · Enter actions · b brief · s resume · n/p column pages · PgUp/PgDn details · Esc close";
    if (this.tab === 3) this.footer = width < 90 ? "v issues/PRs · o state · a step · j/k · PgDn · q" : "v issues/PRs · o state · j/k items · a linked step · Enter linked tasks · n/p pages · PgUp/PgDn details · r refresh · Esc close";
    if (!data) { this.ctx.tui.root.invalidatePaint(); return; }
    if (width < 45 || height < 18) {
      this.put(0, 7, "Resize to at least 45 columns and 19 rows.", width, "WorkBlocked");
      this.ctx.tui.root.invalidatePaint();
      return;
    }
    if (this.tab === 0) this.board(data, width, height);
    else if (this.tab === 1) {
      const rows = /** @type {Line[]} */ ([]);
      this.paragraph(rows, "PROJECT GOAL", data.context.goal, width - 2, "WorkTitle");
      this.paragraph(rows, "DECISIONS", data.context.notes, width - 2, "WorkReview");
      rows.push({ value: "LATEST PROJECT CHECKPOINT", group: "WorkTitle" }, { value: "", group: "WorkText" });
      this.checkpointRows(rows, data.checkpoints[0], width - 2);
      this.paintDetails({ x: 1, y: 7, w: Math.max(1, width - 2), h: Math.max(0, height - 7) }, rows);
    } else if (this.tab === 2) this.checkpoints(data, width, height);
    else this.github(width, height);
    this.ctx.tui.root.invalidatePaint();
  }

  /** @param {BoardSnapshot} data @param {number} width @param {number} height */
  board(data, width, height) {
    const narrow = width < 95;
    const boardWidth = width;
    const top = 7;
    const boardHeight = Math.max(7, Math.floor((height - top) * 0.55));
    const columnWidth = narrow ? boardWidth : Math.floor(boardWidth / STAGES.length);
    const first = narrow ? this.column : 0;
    const last = narrow ? this.column + 1 : STAGES.length;
    if (narrow) {
      let x = 0;
      for (let i = 0; i < STAGES.length; i++) {
        const label = (i === this.column ? "[" : " ") + STAGES[i] + (i === this.column ? "]" : " ");
        const w = Math.min(measure(label), Math.max(0, width - x));
        this.put(x, 6, label, w, GROUPS[i]);
        this.hits.push({ x, y: 6, w, h: 1, kind: "column", column: i, index: 0, action: "" });
        x += w + 1;
      }
    }
    for (let column = first; column < last; column++) {
      const x = narrow ? 0 : column * columnWidth;
      const w = Math.max(1, columnWidth - 1);
      const tasks = this.columns[column];
      const count = data.counts[column];
      this.put(x, top, STAGES[column] + " (" + count + ")", w, GROUPS[column]);
      this.put(x, top + 1, "─".repeat(w), w, GROUPS[column]);
      this.hits.push({ x, y: top, w, h: 2, kind: "column", column, index: 0, action: "" });
      if (!tasks.length) {
        this.put(x + 1, top + 3, column === 4 && !this.includeDone ? "d: show done" : "No tasks", w - 1, "WorkDim");
        continue;
      }
      const visible = Math.max(1, Math.floor(Math.max(0, boardHeight - 3) / 4));
      if (column === this.column) {
        if (this.selected < this.scrolls[column]) this.scrolls[column] = this.selected;
        if (this.selected >= this.scrolls[column] + visible) this.scrolls[column] = this.selected - visible + 1;
      }
      this.scrolls[column] = Math.max(0, Math.min(this.scrolls[column], tasks.length - visible));
      for (let index = this.scrolls[column]; index < Math.min(tasks.length, this.scrolls[column] + visible); index++) {
        const task = tasks[index];
        const y = top + 2 + (index - this.scrolls[column]) * 4;
        const selected = column === this.column && index === this.selected;
        const group = selected ? SELECTED[column] : "WorkCard";
        const h = Math.min(3, Math.max(0, top + boardHeight - 1 - y));
        this.blocks.push({ x, y, w, h, group });
        this.put(x, y, (selected ? "> " : "  ") + task.title, w, selected ? group : "WorkText");
        if (h > 1) this.put(x, y + 1, "  " + (task.notes.replace(/\s+/gu, " ") || "No notes yet"), w, selected ? group : "WorkDim");
        if (h > 2) {
          const state = this.activity.get(this.linkedSession(task));
          const label = (state?.label || (task.session ? "unavailable" : "no linked session")) + " · " + task.id.slice(0, 10);
          const before = this.spans.length;
          this.put(x, y + 2, "  " + (state?.running ? FRAMES[this.frame] : "·") + " " + label, w, selected ? group : GROUPS[column]);
          if (state?.running && this.spans.length > before) this.animatedSpans.push({ spanBorrow: this.spans[this.spans.length - 1], framesOwn: FRAMES.map(frame => clip("  " + frame + " " + label, Math.min(w, this.rect.w - x))) });
        }
        this.hits.push({ x, y, w, h, kind: "card", column, index, action: "" });
      }
      const shown = Math.min(count, data.offsets[column] + tasks.length);
      this.put(x, top + boardHeight - 1, (data.offsets[column] + 1) + "–" + shown + " / " + count + " · n/p", w, "WorkDim");
    }
    const detailRect = { x: 1, y: top + boardHeight + 1, w: Math.max(1, width - 2), h: Math.max(0, height - top - boardHeight - 1) };
    this.put(0, detailRect.y - 1, "─".repeat(width), width, "WorkRule");
    const rows = /** @type {Line[]} */ ([]);
    const task = this.detail?.task || this.selectedTask();
    if (task) {
      this.paragraph(rows, task.status.toUpperCase() + " · SELECTED TASK", task.title, detailRect.w, GROUPS[STATUS.indexOf(task.status)]);
      this.paragraph(rows, "SESSION ACTIVITY", this.activity.get(this.linkedSession(task))?.label || "Unavailable. Task status remains separate.", detailRect.w, "WorkLater");
      this.paragraph(rows, "NOTES", task.notes, detailRect.w, "WorkText");
      if (task.github_url) this.paragraph(rows, "GITHUB · OUTER LOOP", task.github_url, detailRect.w, "WorkLater");
      if (this.detail) this.checkpointRows(rows, this.detail.checkpoint, detailRect.w);
      else rows.push({ value: "Reading linked checkpoint…", group: "WorkDim" });
      this.paragraph(rows, "TASK", task.id, detailRect.w, "WorkDim");
    } else this.checkpointRows(rows, data.checkpoints[0], detailRect.w);
    this.paintDetails(detailRect, rows);
  }

  /** @param {BoardSnapshot} data @param {number} width @param {number} height */
  checkpoints(data, width, height) {
    const listWidth = width;
    const listHeight = Math.max(4, Math.floor((height - 7) * 0.5));
    const visible = Math.max(1, Math.floor(listHeight / 4));
    const first = Math.max(0, this.checkpointIndex - visible + 1);
    for (let i = first; i < Math.min(data.checkpoints.length, first + visible); i++) {
      const checkpoint = data.checkpoints[i];
      const y = 7 + (i - first) * 4;
      const selected = i === this.checkpointIndex;
      const group = selected ? "WorkSelectedLater" : "WorkCard";
      this.blocks.push({ x: 0, y, w: Math.max(1, listWidth - 1), h: Math.min(3, height - y), group });
      this.put(0, y, (selected ? "> " : "  ") + new Date(checkpoint.updated).toISOString().replace("T", " ").slice(0, 19), listWidth - 1, selected ? group : "WorkLater");
      this.put(0, y + 1, "  " + checkpoint.summary.replace(/\s+/gu, " "), listWidth - 1, selected ? group : "WorkText");
      this.put(0, y + 2, checkpoint.stale ? "  STALE · check source" : "  Enter: open source", listWidth - 1, selected ? group : "WorkBlocked");
      this.hits.push({ x: 0, y, w: listWidth - 1, h: 3, kind: "checkpoint", column: 0, index: i, action: "" });
    }
    const rect = { x: 1, y: 8 + listHeight, w: Math.max(1, width - 2), h: Math.max(0, height - listHeight - 8) };
    this.put(0, rect.y - 1, "─".repeat(width), width, "WorkRule");
    const rows = /** @type {Line[]} */ ([]);
    this.checkpointRows(rows, data.checkpoints[this.checkpointIndex], rect.w);
    this.paintDetails(rect, rows);
  }

  /** @param {number} width @param {number} height */
  github(width, height) {
    const data = this.githubData;
    if (!data) {
      this.put(1, 8, this.githubLoading ? "Reading project GitHub work…" : "No GitHub data. Press r to retry.", width - 2, "WorkLater");
      this.put(1, 10, "Read-only. Requires gh and authenticated access.", width - 2, "WorkDim");
      return;
    }
    this.put(0, 6, data.repo + " · " + data.kind + " (" + data.total + ") · " + data.state + " · page " + (this.githubPage + 1), width, "WorkLater");
    const listHeight = Math.max(4, Math.floor((height - 7) * 0.5));
    const visible = Math.max(1, Math.floor(listHeight / 4));
    const first = Math.max(0, this.githubIndex - visible + 1);
    for (let i = first; i < Math.min(data.items.length, first + visible); i++) {
      const item = data.items[i];
      const y = 7 + (i - first) * 4;
      const stage = item.ci === "FAILURE" || item.ci === "ERROR" || item.review === "CHANGES_REQUESTED" ? 2 : item.state === "MERGED" ? 4 : item.state === "CLOSED" ? 3 : item.draft ? 1 : 0;
      const selected = i === this.githubIndex;
      const group = selected ? SELECTED[stage] : "WorkCard";
      this.blocks.push({ x: 0, y, w: width, h: Math.min(3, height - y), group });
      this.put(0, y, (selected ? "> " : "  ") + "#" + item.number + " " + item.title, width, selected ? group : "WorkText");
      this.put(0, y + 1, "  " + item.state + (item.draft ? " · DRAFT" : "") + " · @" + (item.author || "unknown") + (item.labels.length ? " · " + item.labels.join(", ") : ""), width, selected ? group : GROUPS[stage]);
      this.put(0, y + 2, "  " + (item.kind === "pulls" ? "Review: " + (item.review || "not reported") + " · CI: " + (item.ci || "not reported") : item.url), width, selected ? group : "WorkDim");
      this.hits.push({ x: 0, y, w: width, h: 3, kind: "github", column: 0, index: i, action: "" });
    }
    if (!data.items.length) this.put(1, 8, "No " + data.state + " " + data.kind + ".", width - 2, "WorkDim");
    const rect = { x: 1, y: 8 + listHeight, w: Math.max(1, width - 2), h: Math.max(0, height - listHeight - 8) };
    this.put(0, rect.y - 1, "─".repeat(width), width, "WorkRule");
    const rows = /** @type {Line[]} */ ([]);
    const item = this.githubDetail?.item || this.selectedGitHubItem();
    if (item) {
      this.paragraph(rows, "GITHUB · OUTER LOOP", "#" + item.number + " " + item.title, rect.w, "WorkTitle");
      this.paragraph(rows, "SOURCE", item.url, rect.w, "WorkLater");
      if (!this.githubDetail) rows.push({ value: this.githubDetailLoading ? "Reading details…" : "Press r to retry details.", group: "WorkDim" });
      else {
        if (item.kind === "pulls") {
          this.paragraph(rows, "REVIEW / CI (reported by GitHub)", (item.review || "Review not reported") + " · " + (item.ci || "CI not reported"), rect.w, item.ci === "SUCCESS" ? "WorkDone" : "WorkBlocked");
          this.paragraph(rows, "BRANCHES", item.head + " → " + item.base, rect.w, "WorkDim");
          for (let i = 0; i < item.checks.length; i++) {
            const check = item.checks[i];
            rows.push({ value: check.name + " · " + check.status, group: check.status === "SUCCESS" ? "WorkDone" : "WorkBlocked" });
          }
          if (item.more_checks) rows.push({ value: "First 20 CI checks shown; more on GitHub.", group: "WorkDim" });
          rows.push({ value: "", group: "WorkText" });
        }
        rows.push({ value: "INNER TASKS (" + this.githubDetail.linked_task_count + ") · Enter for actions", group: "WorkReview" });
        const linked = this.githubDetail.linked_tasks;
        for (let i = 0; i < linked.length; i++) rows.push({ value: linked[i].status + " · " + linked[i].title, group: GROUPS[STATUS.indexOf(linked[i].status)] });
        if (!linked.length) rows.push({ value: "a: add a linked internal step. GitHub stays unchanged.", group: "WorkDim" });
        if (this.githubDetail.linked_task_count > linked.length) rows.push({ value: "First 50 linked tasks shown.", group: "WorkDim" });
        rows.push({ value: "", group: "WorkText" });
        this.paragraph(rows, "BODY PREVIEW (up to 300 rows)", item.body, rect.w, "WorkText");
      }
    }
    this.paintDetails(rect, rows);
  }

  /** @param {Parameters<Window["onKey"]>[0]} event */
  onKey(event) {
    if (event.type !== "key" || event.event === "release") return true;
    const stroke = keys.strokeOf(event);
    if (stroke === "esc" || stroke === "q" || stroke === "ctrl+c") this.close();
    else if (stroke === "1" || stroke === "2" || stroke === "3" || stroke === "4") this.selectTab(Number(stroke) - 1);
    else if (stroke === "tab") this.selectTab(this.tab + 1);
    else if (stroke === "shift+tab") this.selectTab(this.tab - 1);
    else if (stroke === "left" || stroke === "h") this.tab === 0 ? this.moveColumn(-1) : this.tab === 3 ? void this.act("github_kind") : this.selectTab(this.tab - 1);
    else if (stroke === "right" || stroke === "l") this.tab === 0 ? this.moveColumn(1) : this.tab === 3 ? void this.act("github_kind") : this.selectTab(this.tab + 1);
    else if (stroke === "up" || stroke === "k") this.move(-1);
    else if (stroke === "down" || stroke === "j") this.move(1);
    else if (stroke === "page_down" || stroke === "pagedown" || stroke === "ctrl+d") { this.detailScroll += Math.max(1, this.detailRect.h - 1); this.rebuild(); }
    else if (stroke === "page_up" || stroke === "pageup" || stroke === "ctrl+u") { this.detailScroll = Math.max(0, this.detailScroll - Math.max(1, this.detailRect.h - 1)); this.rebuild(); }
    else if (stroke === "r") this.tab === 3 ? void this.refreshGitHub() : void this.refresh();
    else if (stroke === "n") this.tab === 3 ? this.pageGitHub(1) : this.page(1);
    else if (stroke === "p") this.tab === 3 ? this.pageGitHub(-1) : this.page(-1);
    else if (stroke === "v" && this.tab === 3) void this.act("github_kind");
    else if (stroke === "o" && this.tab === 3) void this.act("github_state");
    else if (stroke === "d") void this.act("done");
    else if (stroke === "/") void this.act("search");
    else if (stroke === "a") void this.act(this.tab === 3 ? "github_add" : "add");
    else if (stroke === "m") void this.act("status");
    else if (stroke === "c") void this.act("checkpoint");
    else if (stroke === "g") void this.act("context");
    else if (stroke === "b" && this.tab === 0) void this.act("prepare");
    else if (stroke === "s") void this.act("resume");
    else if (stroke === "enter") void this.act(this.tab === 3 ? "github_task" : this.tab === 2 ? "resume" : this.tab === 0 ? "task" : "context");
    return true;
  }

  /** @param {Parameters<Window["onMouse"]>[0]} event */
  onMouse(event) {
    if (event.event !== "press") return true;
    const x = event.col - this.rect.x;
    const y = event.row - this.rect.y;
    if (event.button === "wheel_up" || event.button === "wheel_down") {
      const delta = (event.button === "wheel_up" ? -3 : 3) * (event.count || 1);
      const detail = this.detailRect;
      if (x >= detail.x && x < detail.x + detail.w && y >= detail.y && y < detail.y + detail.h) {
        this.detailScroll = Math.max(0, this.detailScroll + delta);
        this.rebuild();
      } else this.move(delta);
      return true;
    }
    if (event.button !== "left") return true;
    for (let i = 0; i < this.hits.length; i++) {
      const hit = this.hits[i];
      if (x < hit.x || x >= hit.x + hit.w || y < hit.y || y >= hit.y + hit.h) continue;
      if (hit.kind === "tab") this.selectTab(hit.index);
      else if (hit.kind === "control") hit.action === "refresh" ? void this.refresh() : hit.action === "github_refresh" ? void this.refreshGitHub() : void this.act(hit.action);
      else if (hit.kind === "github") { this.githubIndex = hit.index; this.detailScroll = 0; this.loadGitHubDetail(); this.rebuild(); if (event.count >= 2) void this.act("github_task"); }
      else if (hit.kind === "checkpoint") { this.checkpointIndex = hit.index; this.detailScroll = 0; this.rebuild(); if (event.count >= 2) void this.act("resume"); }
      else {
        this.column = hit.column;
        this.selected = hit.index;
        this.detailScroll = 0;
        this.loadDetail();
        this.rebuild();
        if (hit.kind === "card" && event.count >= 2) void this.act("task");
      }
      break;
    }
    return true;
  }
}
