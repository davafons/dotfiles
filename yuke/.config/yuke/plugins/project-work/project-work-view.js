/** @import { UiBorrow } from "../../types.js" */
//! Full-screen project work. Layout and state changes build the paint cache; draw only paints it.
import { clip, fill, keys, measure, text, Window, Document } from "yuke:ui";
import { wrapRows } from "yuke:chat";

/** @import { Rect } from "yuke:ui" */
/** @import { Observation } from "./activity.js" */
/** @import { GitHubItem, GitHubPage, GitHubDetail } from "./project-work-github.js" */
/** @typedef {{ id: string, title: string, status: string, notes: string, session: string, root: string, updated: number, version: number, github_url: string, owner_session?: string, owner_root?: string }} Task */
/** @typedef {{ session: string, root: string, body: string, updated: number }} TaskMessage */
/** @typedef {{ project: string, name: string, root: string, tasks: Task[], counts: number[], offsets: number[], query: string, include_done: boolean, owner_counts?: Record<string, number> }} BoardSnapshot */
/** @typedef {{ activityRead?: (ids: string[]) => Promise<Map<string, Observation>>, read: (offsets: number[], query: string, done: boolean) => Promise<BoardSnapshot>, detail: (id: string) => Promise<{task: Task, messages?: TaskMessage[]}>, githubRead: (args: Record<string, unknown>) => Promise<GitHubPage>, githubDetail: (args: Record<string, unknown>) => Promise<GitHubDetail>, action: (name: string, task: Task | null) => Promise<"close" | void> }} Actions */
/** @typedef {{x: number, y: number, value: string, group: string}} Span */
/** @typedef {{x: number, y: number, w: number, h: number, group: string}} Block */
/** @typedef {{x: number, y: number, w: number, h: number, kind: string, column: number, index: number, action: string}} Hit */
/** @typedef {{value: string, group: string, segments?: {text: string, group: string}[]}} Line */

const STAGES = ["Now", "Later", "Blocked", "Review", "Done"];
const STATUS = ["now", "later", "blocked", "review", "done"];
const GROUPS = ["WorkNow", "WorkLater", "WorkBlocked", "WorkReview", "WorkDone"];
const SELECTED = ["WorkSelectedNow", "WorkSelectedLater", "WorkSelectedBlocked", "WorkSelectedReview", "WorkSelectedDone"];
const TABS = ["Board", "GitHub"];
const ACTIVE_FIRST = [0, 2, 3, 1, 4];
const TASK_ACTIONS = [
  { key: "s", label: "Open assigned chat", action: "session" },
  { key: "b", label: "Prepare brief", action: "prepare" },
  { key: "o", label: "Assign to this chat", action: "claim" },
  { key: "u", label: "Unassign task", action: "release" },
  { key: "t", label: "Post message", action: "message" },
  { key: "e", label: "Edit notes", action: "notes" },
  { key: "m", label: "Change status", action: "status" },
];
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
    /** @type {Task | null} */
    this.taskFocus = null;
    this.actionIndex = 0;
    this.actionsFocused = true;
    this.column = 0;
    this.selected = 0;
    this.detailScroll = 0;
    this.scrolls = [0, 0, 0, 0, 0];
    /** @type {("auto" | "expanded" | "collapsed")[]} */
    this.columnModes = ["auto", "auto", "auto", "auto", "auto"];
    this.peekColumn = -1;
    this.offsets = [0, 0, 0, 0, 0];
    this.pageDirection = 0;
    this.query = "";
    this.includeDone = false;
    this.refreshMode = "idle";
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
    /** @type {{task: Task, messages?: TaskMessage[]} | null} */
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

  /** Read only the session assigned to this task. @param {Task} task @returns {string} */
  linkedSession(task) {
    return task.owner_session || "";
  }

  /** Read a bounded live snapshot outside drawing. Closed or replaced boards reject late results. */
  async refreshActivity() {
    const data = this.data;
    if (this.closed || this.activityPending || !data || !this.actions.activityRead) return;
    this.activityPending = true;
    try {
      const ids = [...Object.keys(data.owner_counts || {}), ...data.tasks.map(task => this.linkedSession(task))];
      if (this.taskFocus) ids.push(this.linkedSession(this.taskFocus));
      const observed = await this.actions.activityRead(ids);
      if (this.closed || this.data !== data) return;
      let changed = observed.size !== this.activity.size;
      observed.forEach((value, id) => { if (JSON.stringify(this.activity.get(id)) !== JSON.stringify(value)) changed = true; });
      if (changed) { this.activity = observed; this.rebuild(); }
      if (Object.keys(data.owner_counts || {}).some(id => observed.get(id)?.presence === "closed")) await this.refresh(true);
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

  get loading() { return this.refreshMode === "blocking"; }

  /** @returns {Task | null} */
  selectedTask() { return this.taskFocus || this.columns[this.column]?.[this.selected] || null; }

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

  /** @param {boolean} [quiet] */
  async refresh(quiet = false) {
    if (this.closed || this.refreshMode === "blocking" || (quiet && (this.pending || this.refreshMode !== "idle"))) return;
    const generation = ++this.generation;
    const selectedId = this.selectedTask()?.id;
    this.refreshMode = quiet ? "quiet" : "blocking";
    if (!quiet) { this.error = ""; this.rebuild(); }
    const scroll = this.detailScroll;
    try {
      const data = await this.actions.read(this.offsets, this.query, this.includeDone);
      if (this.closed || generation !== this.generation) return;
      if (quiet && JSON.stringify(data) === JSON.stringify(this.data)) {
        if (this.taskFocus) this.loadDetail();
        return;
      }
      this.data = data;
      this.offsets = data.offsets.slice();
      this.columns = STATUS.map((status) => data.tasks.filter((task) => task.status === status));
      let found = false;
      for (let column = 0; column < this.columns.length; column++) {
        const index = this.columns[column].findIndex((task) => task.id === selectedId);
        if (index >= 0) { this.selectColumn(column); this.selected = index; found = true; break; }
      }
      if (!found) {
        if (!this.columns[this.column].length) this.selectColumn(ACTIVE_FIRST.find((column) => this.columns[column].length > 0) ?? 0);
        this.selected = this.pageDirection < 0 ? Math.max(0, this.columns[this.column].length - 1) : 0;
      }
      this.pageDirection = 0;
      this.detailScroll = quiet ? scroll : 0;
      this.loadDetail();
      void this.refreshActivity();
    } catch (error) {
      if (!this.closed && generation === this.generation) this.error = String(error);
    } finally {
      if (!this.closed && generation === this.generation) { this.refreshMode = "idle"; this.rebuild(); }
    }
  }

  loadDetail() {
    const task = this.selectedTask();
    const generation = ++this.detailGeneration;
    if (this.detail?.task.id !== task?.id) this.detail = null;
    if (!task || this.closed) return;
    void this.actions.detail(task.id).then((detail) => {
      if (this.closed || generation !== this.detailGeneration || this.selectedTask()?.id !== detail.task.id) return;
      this.detail = detail;
      if (this.taskFocus) this.taskFocus = detail.task;
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
        if (await this.actions.action(name, this.tab === 0 ? this.selectedTask() : null) === "close") {
          this.close();
          return;
        }
      }
      if (!this.closed) {
        await this.refresh();
        if (this.tab === 1) this.loadGitHubDetail();
      }
    } catch (error) {
      if (!this.closed) this.error = String(error);
    } finally {
      this.pending = false;
      if (!this.closed) this.rebuild();
    }
  }

  /** Open a task inspector without changing its ownership or starting a run. @param {Task | null} task */
  inspect(task = this.selectedTask()) {
    if (!task) return;
    this.taskFocus = task;
    this.tab = 0;
    this.detailScroll = 0;
    this.actionIndex = 0;
    this.actionsFocused = true;
    this.loadDetail();
    this.rebuild();
  }

  /** @param {number} tab */
  selectTab(tab) {
    this.taskFocus = null;
    this.peekColumn = -1;
    this.tab = (tab + TABS.length) % TABS.length;
    this.detailScroll = 0;
    if (this.tab === 1 && !this.githubData) void this.refreshGitHub();
    this.rebuild();
  }

  /** @param {number} column @param {boolean} [includePeek] */
  columnCollapsed(column, includePeek = true) {
    if (includePeek && this.peekColumn === column) return false;
    return this.columnModes[column] === "collapsed" || (this.columnModes[column] === "auto" && !this.columns[column].length);
  }

  /** @param {number} column */
  selectColumn(column) {
    if (this.column !== column) this.peekColumn = -1;
    this.column = column;
  }

  /** @param {number} [column] */
  toggleColumn(column = this.column) {
    this.columnModes[column] = this.columnCollapsed(column, false) ? "expanded" : "collapsed";
    this.peekColumn = -1;
    this.rebuild();
  }

  /** @param {number} width */
  columnLayouts(width) {
    const narrow = width < 95;
    const compact = 4;
    const collapsed = STATUS.map((_, column) => this.columnCollapsed(column));
    const openCount = collapsed.filter(value => !value).length;
    const available = width - collapsed.filter(Boolean).length * compact;
    let extra = openCount ? available % openCount : 0;
    let x = 0;
    return STATUS.map((_, column) => {
      const cellWidth = collapsed[column] ? compact : narrow ? width : Math.floor(available / openCount) + (extra-- > 0 ? 1 : 0);
      const rect = { column, x: narrow ? 0 : x, w: Math.max(1, cellWidth - 1), collapsed: collapsed[column] };
      x += cellWidth;
      return rect;
    }).filter(rect => !narrow || rect.column === this.column);
  }

  /** @param {number} delta */
  moveColumn(delta) {
    this.selectColumn((this.column + delta + STAGES.length) % STAGES.length);
    this.selected = Math.min(this.selected, Math.max(0, this.columns[this.column].length - 1));
    this.detailScroll = 0;
    this.loadDetail();
    this.rebuild();
  }

  /** @param {number} delta */
  move(delta) {
    if (this.tab === 1) {
      const next = Math.max(0, Math.min(this.githubIndex + delta, (this.githubData?.items.length || 0) - 1));
      if (next === this.githubIndex) return;
      this.githubIndex = next;
      this.detailScroll = 0;
      this.loadGitHubDetail();
    } else if (this.tab === 0) {
      if (this.columnCollapsed(this.column)) this.peekColumn = this.column;
      if (delta > 0 && this.selected + delta >= this.columns[this.column].length && this.data && this.offsets[this.column] + this.columns[this.column].length < this.data.counts[this.column]) { this.page(1); return; }
      if (delta < 0 && this.selected === 0 && this.offsets[this.column] > 0) { this.page(-1); return; }
      this.selected = Math.max(0, Math.min(this.selected + delta, this.columns[this.column].length - 1));
      this.detailScroll = 0;
      this.loadDetail();
    }
    this.rebuild();
  }

  /** @param {number} delta */
  page(delta) {
    if (this.loading || this.pending || !this.data) return;
    const next = Math.max(0, this.offsets[this.column] + delta * 5);
    if (next >= this.data.counts[this.column] && next > 0) return;
    this.offsets[this.column] = next;
    this.pageDirection = delta;
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
      if (row.segments) {
        let x = rect.x;
        for (let segment = 0; segment < row.segments.length; segment++) {
          const part = row.segments[segment];
          this.put(x, rect.y + i, part.text, rect.x + rect.w - x, part.group);
          x += measure(part.text);
        }
      } else this.put(rect.x, rect.y + i, row.value, rect.w, row.group);
    }
    if (scrollable && rect.h > 0) this.put(rect.x, rect.y + rect.h - 1,
      (this.detailScroll ? "↑ " : "") + (this.detailScroll + 1) + "-" + Math.min(lines.length, this.detailScroll + visible) + "/" + lines.length +
      (this.detailScroll + visible < lines.length ? " ↓" : " · end") + " · PgUp/PgDn", rect.w, "WorkShortcut");
  }

  /** @param {Line[]} rows @param {string} label @param {string} value @param {number} width @param {string} group @param {boolean} [markdown] */
  paragraph(rows, label, value, width, group, markdown = false) {
    rows.push({ value: label, group: "WorkDim" });
    if (markdown) {
      const document = new Document();
      document.setText(value || "Not recorded");
      const wrapped = document.rows(Math.max(1, width), 4000);
      for (let i = 0; i < wrapped.length; i++) {
        const segments = wrapped[i].segments;
        rows.push({ value: segments.map(segment => segment.text).join(""), group, segments });
      }
    } else {
      const wrapped = wrapRows(value || "Not recorded", Math.max(1, width), group, 0, 4000);
      for (let i = 0; i < wrapped.length; i++) {
        const row = wrapped[i];
        rows.push({ value: row.text || row.segments?.map(segment => segment.text).join("") || "", group });
      }
    }
    rows.push({ value: "", group: "WorkText" });
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
    this.put(0, 3, data?.root || "Reading project work…", width, "WorkDim");
    const controls = this.tab === 1 ? [["v " + (this.githubKind === "issues" ? "Issues" : "PRs"), "github_kind"], ["o " + this.githubState, "github_state"], ["a Internal step", "github_add"], ["r Refresh", "github_refresh"]] : [["a Add", "add"], ["m Status", "status"], ["/ Filter", "search"], [this.includeDone ? "Hide done" : "Show done", "done"], ["r Refresh", "refresh"]];
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
    else if (data?.owner_counts) {
      const tasks = Object.values(data.owner_counts).reduce((total, count) => total + count, 0);
      this.put(0, 5, tasks + (tasks === 1 ? " assigned task" : " assigned tasks") + " · One task per session", width, "WorkLater");
    }
    else this.put(0, 5, data?.root || "Reading project work…", width, "WorkDim");
    const folding = this.peekColumn === this.column ? "z keep open" : this.columnCollapsed(this.column) ? "z expand" : "z fold";
    this.footer = width < 90 ? "h/l columns · j/k cards · " + folding + " · Enter actions · q close" : "h/l columns · j/k scroll · " + folding + " · Z auto · Enter inspect · s assigned chat · n/p pages · PgUp/PgDn details · Esc close";
    if (this.tab === 1) this.footer = width < 90 ? "v issues/PRs · o state · a step · j/k · PgDn · q" : "v issues/PRs · o state · j/k items · a linked step · Enter linked tasks · n/p pages · PgUp/PgDn details · r refresh · Esc close";
    if (!data) { this.ctx.tui.root.invalidatePaint(); return; }
    if (width < 45 || height < 18) {
      this.put(0, 7, "Resize to at least 45 columns and 19 rows.", width, "WorkBlocked");
      this.ctx.tui.root.invalidatePaint();
      return;
    }
    if (this.taskFocus) this.inspector(width, height);
    else if (this.tab === 0) this.board(data, width, height);
    else this.github(width, height);
    this.ctx.tui.root.invalidatePaint();
  }

  /** @param {BoardSnapshot} data @param {number} width @param {number} height */
  board(data, width, height) {
    const narrow = width < 95;
    const top = 7;
    const boardHeight = Math.max(7, Math.floor((height - top) * 0.55));
    const layouts = this.columnLayouts(width);
    if (narrow) {
      let x = 0;
      for (let i = 0; i < STAGES.length; i++) {
        const label = (i === this.column ? "[" : " ") + STAGES[i] + (i === this.column ? "]" : " ");
        const w = Math.min(measure(label), Math.max(0, width - x));
        this.put(x, 6, label, w, GROUPS[i]);
        this.hits.push({ x, y: 6, w, h: 1, kind: "column_tab", column: i, index: 0, action: "" });
        x += w + 1;
      }
    }
    for (let layout = 0; layout < layouts.length; layout++) {
      const { column, x, w, collapsed } = layouts[layout];
      const tasks = this.columns[column];
      const count = data.counts[column];
      const headingGroup = column === this.column ? SELECTED[column] : GROUPS[column];
      this.hits.push({ x, y: top, w, h: collapsed ? boardHeight : 2, kind: "column", column, index: 0, action: "" });
      if (collapsed) {
        this.put(x + 1, top, "▸", 1, headingGroup);
        const label = STAGES[column].length <= boardHeight - 4 ? STAGES[column] : ["Now", "Later", "Block", "Rev", "Done"][column];
        for (let row = 0; row < Math.min(label.length, boardHeight - 4); row++) this.put(x + 1, top + 2 + row, label[row], 1, GROUPS[column]);
        this.put(x, top + boardHeight - 2, count > 99 ? "99+" : String(count), w, GROUPS[column]);
        this.put(x + 1, top + boardHeight - 1, "z", 1, "WorkShortcut");
        continue;
      }
      this.put(x, top, "▾ " + STAGES[column] + " (" + count + ")", w, headingGroup);
      this.put(x, top + 1, "─".repeat(w), w, GROUPS[column]);
      if (!tasks.length) {
        this.put(x + 1, top + 3, column === 4 && !this.includeDone ? "Use Show done above" : "No tasks", w - 1, "WorkDim");
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
        if (h > 1) {
          const owner = task.owner_session ? this.activity.get(task.owner_session) : null;
          this.put(x, y + 1, "  " + (task.owner_session ? (owner?.ownerLabel || "Chat " + task.owner_session.slice(-8)) + (owner?.title ? " · " + owner.title : "") : "Not assigned"), w, selected ? group : "WorkDim");
        }
        if (h > 2) {
          const state = task.owner_session ? this.activity.get(task.owner_session) : null;
          const label = task.owner_session ? (state?.label || "unavailable") : "Enter: task actions";
          const before = this.spans.length;
          this.put(x, y + 2, "  " + (state?.running ? FRAMES[this.frame] : "·") + " " + label, w, selected ? group : GROUPS[column]);
          if (state?.running && this.spans.length > before) this.animatedSpans.push({ spanBorrow: this.spans[this.spans.length - 1], framesOwn: FRAMES.map(frame => clip("  " + frame + " " + label, Math.min(w, this.rect.w - x))) });
        }
        this.hits.push({ x, y, w, h, kind: "card", column, index, action: "" });
      }
      const start = data.offsets[column] + this.scrolls[column];
      const end = Math.min(count, data.offsets[column] + Math.min(tasks.length, this.scrolls[column] + visible));
      this.put(x, top + boardHeight - 1, (start ? "↑ " : "") + (start + 1) + "-" + end + "/" + count +
        (end < count ? " ↓" : " · end"), w, "WorkShortcut");
      const railX = x + w - 1;
      const railHeight = Math.max(1, boardHeight - 3);
      if (count > visible) {
        const thumbHeight = Math.max(1, Math.floor(visible / count * railHeight));
        const thumbTop = Math.min(railHeight - thumbHeight, Math.floor(start / Math.max(1, count - visible) * (railHeight - thumbHeight)));
        for (let row = 0; row < railHeight; row++) this.put(railX, top + 2 + row, row >= thumbTop && row < thumbTop + thumbHeight ? "█" : "│", 1, GROUPS[column]);
      }
      if (column === this.column) {
        if (data.offsets[column] > 0) this.hits.push({ x, y: top + boardHeight - 1, w: Math.floor(w / 2), h: 1, kind: "page", column, index: -1, action: "" });
        if (data.offsets[column] + tasks.length < count) this.hits.push({ x: x + Math.floor(w / 2), y: top + boardHeight - 1, w: w - Math.floor(w / 2), h: 1, kind: "page", column, index: 1, action: "" });
      }
    }
    const detailRect = { x: 1, y: top + boardHeight + 1, w: Math.max(1, width - 2), h: Math.max(0, height - top - boardHeight - 1) };
    this.put(0, detailRect.y - 1, "─".repeat(width), width, "WorkRule");
    const rows = /** @type {Line[]} */ ([]);
    const task = this.detail?.task || this.selectedTask();
    if (task) this.taskRows(rows, task, detailRect.w);
    else rows.push({ value: "No task selected. Press a to add one.", group: "WorkDim" });
    this.paintDetails(detailRect, rows);
  }

  /** @param {Line[]} rows @param {Task} task @param {number} width */
  taskRows(rows, task, width) {
    this.paragraph(rows, task.status.toUpperCase() + " · SELECTED TASK", task.title, width, GROUPS[STATUS.indexOf(task.status)]);
    const owner = task.owner_session ? this.activity.get(task.owner_session) : null;
    if (task.owner_session && owner) {
      this.paragraph(rows, "ASSIGNED AGENT", (owner.ownerLabel || "Chat") + " · " + (owner.title || "Untitled chat"), width, "WorkTitle");
      if (owner.model) this.paragraph(rows, "MODEL", owner.model, width, "WorkDim");
      if (owner.parent) this.paragraph(rows, "PARENT CHAT", owner.parent, width, "WorkDim");
    }
    this.paragraph(rows, "ASSIGNED SESSION", task.owner_session ? task.owner_session + "\n\n" + (task.owner_root || "Checkout not recorded") : "Not assigned to a session. Use Assign to this chat to start.", width, "WorkLater");
    if (task.owner_session) this.paragraph(rows, "SESSION ACTIVITY", this.activity.get(task.owner_session)?.label || "Unavailable. Task status remains separate.", width, "WorkLater");
    this.paragraph(rows, "NOTES", task.notes, width, "WorkText", true);
    if (task.github_url) this.paragraph(rows, "GITHUB · OUTER LOOP", task.github_url, width, "WorkLater");
    const messages = this.detail?.messages || [];
    if (messages.length) {
      rows.push({ value: "TASK MESSAGES · latest 20 · refresh to read replies", group: "WorkTitle" });
      for (let i = 0; i < messages.length; i++) {
        const message = messages[i];
        this.paragraph(rows, message.session + " · " + new Date(message.updated).toISOString(), message.body, width, "WorkText", true);
      }
    }
    this.paragraph(rows, "TASK", task.id, width, "WorkDim");
  }

  taskActions() {
    return TASK_ACTIONS.filter(action => this.selectedTask()?.owner_session || (action.action !== "session" && action.action !== "release"));
  }

  /** @param {number} width @param {number} height */
  inspector(width, height) {
    const railWidth = Math.min(27, Math.floor(width * 0.4));
    const railX = width - railWidth;
    const rows = /** @type {Line[]} */ ([]);
    const task = this.detail?.task || this.taskFocus;
    if (task) this.taskRows(rows, task, railX - 3);
    this.paintDetails({ x: 1, y: 7, w: railX - 3, h: height - 7 }, rows);
    for (let y = 7; y < height; y++) this.put(railX - 1, y, "│", 1, "WorkRule");
    this.put(railX + 1, 7, "TASK ACTIONS", railWidth - 2, "WorkTitle");
    const actions = this.taskActions();
    this.actionIndex = Math.min(this.actionIndex, actions.length - 1);
    for (let i = 0; i < actions.length; i++) {
      const action = actions[i];
      const group = this.actionsFocused && this.actionIndex === i ? "WorkSelectedLater" : "WorkShortcut";
      const label = action.label;
      this.put(railX + 1, 9 + i, action.key + " " + label, railWidth - 2, group);
      this.hits.push({ x: railX, y: 9 + i, w: railWidth, h: 1, kind: "control", column: 0, index: i, action: action.action });
    }
    this.footer = "↑/↓ actions · ← details · → actions · PgUp/PgDn scroll · Esc board";
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
        this.paragraph(rows, "BODY PREVIEW", item.body, rect.w, "WorkText", true);
      }
    }
    this.paintDetails(rect, rows);
  }

  /** @param {Parameters<Window["onKey"]>[0]} event */
  onKey(event) {
    if (event.type !== "key" || event.event === "release") return true;
    const stroke = keys.strokeOf(event);
    if (this.taskFocus) {
      const actions = this.taskActions();
      if (stroke === "esc" || stroke === "q") { this.taskFocus = null; this.detailScroll = 0; this.loadDetail(); this.rebuild(); return true; }
      if (stroke === "left" || stroke === "h") { this.actionsFocused = false; this.rebuild(); return true; }
      if (stroke === "right" || stroke === "l") { this.actionsFocused = true; this.rebuild(); return true; }
      if (stroke === "up" || stroke === "k" || stroke === "down" || stroke === "j") {
        const delta = stroke === "up" || stroke === "k" ? -1 : 1;
        if (this.actionsFocused) this.actionIndex = (this.actionIndex + delta + actions.length) % actions.length;
        else this.detailScroll = Math.max(0, this.detailScroll + delta);
        this.rebuild(); return true;
      }
      if (stroke === "enter") { if (this.actionsFocused) void this.act(actions[this.actionIndex].action); return true; }
      const action = actions.find(action => action.key === stroke);
      if (action) { void this.act(action.action); return true; }
    }
    if (stroke === "esc" || stroke === "q" || stroke === "ctrl+c") this.close();
    else if (stroke === "1" || stroke === "2") this.selectTab(Number(stroke) - 1);
    else if (stroke === "tab") this.selectTab(this.tab + 1);
    else if (stroke === "shift+tab") this.selectTab(this.tab - 1);
    else if (stroke === "left" || stroke === "h") this.tab === 0 ? this.moveColumn(-1) : void this.act("github_kind");
    else if (stroke === "right" || stroke === "l") this.tab === 0 ? this.moveColumn(1) : void this.act("github_kind");
    else if (stroke === "up" || stroke === "k") this.move(-1);
    else if (stroke === "down" || stroke === "j") this.move(1);
    else if (stroke === "page_down" || stroke === "pagedown" || stroke === "ctrl+d") { this.detailScroll += Math.max(1, this.detailRect.h - 1); this.rebuild(); }
    else if (stroke === "page_up" || stroke === "pageup" || stroke === "ctrl+u") { this.detailScroll = Math.max(0, this.detailScroll - Math.max(1, this.detailRect.h - 1)); this.rebuild(); }
    else if (stroke === "z" && this.tab === 0 && !this.taskFocus) this.toggleColumn();
    else if (stroke === "Z" && this.tab === 0 && !this.taskFocus) { this.columnModes.fill("auto"); this.peekColumn = -1; this.rebuild(); }
    else if (stroke === "r") this.tab === 1 ? void this.refreshGitHub() : void this.refresh();
    else if (stroke === "n" && !this.taskFocus) this.tab === 1 ? this.pageGitHub(1) : this.page(1);
    else if (stroke === "p" && !this.taskFocus) this.tab === 1 ? this.pageGitHub(-1) : this.page(-1);
    else if (stroke === "v" && this.tab === 1) void this.act("github_kind");
    else if (stroke === "o" && this.tab === 1) void this.act("github_state");
    else if (stroke === "/") void this.act("search");
    else if (stroke === "a") void this.act(this.tab === 1 ? "github_add" : "add");
    else if (stroke === "m") void this.act("status");
    else if (stroke === "b" && this.tab === 0) void this.act("prepare");
    else if (stroke === "s" && this.tab === 0) void this.act("session");
    else if (stroke === "enter") { if (this.tab === 0 && this.columnCollapsed(this.column)) this.toggleColumn(); else if (this.tab === 0) this.inspect(); else void this.act("github_task"); }
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
      } else if (!this.taskFocus) {
        const card = this.hits.find(hit => (hit.kind === "card" || hit.kind === "column") && x >= hit.x && x < hit.x + hit.w);
        if (card && this.tab === 0) { this.selectColumn(card.column); this.selected = Math.min(this.selected, Math.max(0, this.columns[this.column].length - 1)); }
        this.move(delta);
      }
      return true;
    }
    if (event.button !== "left") return true;
    for (let i = 0; i < this.hits.length; i++) {
      const hit = this.hits[i];
      if (x < hit.x || x >= hit.x + hit.w || y < hit.y || y >= hit.y + hit.h) continue;
      if (hit.kind === "page") { this.selectColumn(hit.column); this.page(hit.index); }
      else if (hit.kind === "tab") this.selectTab(hit.index);
      else if (hit.kind === "column") { this.selectColumn(hit.column); this.selected = Math.min(this.selected, Math.max(0, this.columns[this.column].length - 1)); this.detailScroll = 0; this.loadDetail(); this.toggleColumn(hit.column); }
      else if (hit.kind === "control") hit.action === "refresh" ? void this.refresh() : hit.action === "github_refresh" ? void this.refreshGitHub() : void this.act(hit.action);
      else if (hit.kind === "github") { this.githubIndex = hit.index; this.detailScroll = 0; this.loadGitHubDetail(); this.rebuild(); if (event.count >= 2) void this.act("github_task"); }
      else {
        this.selectColumn(hit.column);
        this.selected = hit.index;
        this.detailScroll = 0;
        this.loadDetail();
        this.rebuild();
        if (hit.kind === "card") {
          const task = this.selectedTask();
          if (task?.owner_session) void this.act("session");
          else if (event.count >= 2) this.inspect();
        }
      }
      break;
    }
    return true;
  }
}


/** Cached assignment rows for visible sessions. Storage reads never run during strip layout or drawing. */
export class SessionTaskIndicator {
  /** @param {(session: string) => Promise<{tasks: {id: string, title: string, status: string}[], total: number}>} read @param {() => void} changed */
  constructor(read, changed) {
    this.read = read;
    this.changed = changed;
    this.closed = false;
    /** @type {Map<string, {pending: boolean, text: string, group: string}>} */
    this.entries = new Map();
  }

  /** @param {string[]} sessions */
  async refresh(sessions) {
    if (this.closed) return;
    const visible = new Set(sessions.filter(Boolean));
    for (const id of this.entries.keys()) if (!visible.has(id)) this.entries.delete(id);
    await Promise.all(Array.from(visible, async id => {
      let entry = this.entries.get(id);
      if (entry?.pending) return;
      if (!entry) {
        entry = {pending:false, text:"Task: reading assignment…", group:"WorkDim"};
        this.entries.set(id, entry);
      }
      const held = entry;
      held.pending = true;
      try {
        const result = await this.read(id);
        if (this.closed || this.entries.get(id) !== held) return;
        if (result.total > 1) {
          held.text = `Task: ${result.total} conflicting assignments · /work to resolve`;
          held.group = "WorkDanger";
        } else if (result.total === 1 && result.tasks[0]) {
          const task = result.tasks[0];
          held.text = `Task [${task.status}]: ${task.title} · /work`;
          held.group = GROUPS[STATUS.indexOf(task.status)] || "WorkTitle";
        } else {
          held.text = "Task: not assigned · /work to assign";
          held.group = "WorkDim";
        }
      } catch {
        if (this.closed || this.entries.get(id) !== held) return;
        held.text = "Task: assignment unavailable · /work to retry";
        held.group = "WorkDanger";
      } finally {
        held.pending = false;
        if (!this.closed && this.entries.get(id) === held) this.changed();
      }
    }));
  }

  /** @param {string | null} session @param {number} width */
  row(session, width) {
    const entry = session ? this.entries.get(session) : null;
    return {text:clip(entry?.text || (session ? "Task: reading assignment…" : "Task: not assigned · /work to assign"), Math.max(0, width), true), group:entry?.group || "WorkDim"};
  }

  close() { this.closed = true; this.entries.clear(); }
}
