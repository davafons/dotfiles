//! Manifest entry with context-owned registrations and explicit resource lifetimes.
/** @import { UiBorrow } from "../../types.js" */
import { env, exec, fs } from "yuke";
import { currentEntry, currentPane, showSession } from "yuke:session";
import { Window, clip, keys, measure, text } from "yuke:ui";

/** @typedef {{name: string, input: number, output: number, reasoning: number, cache_read: number, cache_write: number, cost: number, withoutCache: number, unpriced: number, unreported: number, messages: number, tools: number}} UsageBucket */
/** @typedef {UsageBucket & {date: string}} Day */
/** @typedef {{name: string, uses: number, invocations: number, reads: number}} Skill */
/** @typedef {{name: string, calls: number, errors: number, canceled: number, durationMs: number}} Tool */
/** @typedef {{id: string, title: string, root: string, kind: string, model: string, created: number, updated: number, messages: number, input: number, output: number, cost: number, unpriced: number, activeMs: number, elapsedMs: number}} Chat */
/** @typedef {{asOf: string, scope: string | null, totals: UsageBucket, daily: Day[], models: UsageBucket[], providers: UsageBucket[], roles: Record<string, number>, finishes: Record<string, number>, outcomes: Record<string, number>, efforts: {name: string, count: number}[], tools: Tool[], skills: Skill[], catalogSkills: number, chats: Chat[], chatCount: number, childCount: number, activeMs: number, completedRuns: number, longestChatMs: number, currentStreak: number, longestStreak: number, notes: string[]}} Snapshot */
/** @typedef {{x: number, value: string, group: string}} Span */
/** @typedef {{spans: Span[], chat?: Chat}} Row */

const TABS = ["Overview", "Usage", "Messages", "Plugins", "Skills", "Chats"];
const PERIODS = ["Daily", "Weekly", "Monthly"];
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const EMPTY_RECT = { x: 0, y: 0, w: 0, h: 0 };

/** @param {number} value */
function number(value) { return String(Math.round(value)).replace(/\B(?=(\d{3})+(?!\d))/g, ","); }
/** @param {number} value @param {string} noun @param {string} [plural] */
function countLabel(value, noun, plural = noun + "s") { return number(value) + " " + (value === 1 ? noun : plural); }
/** @param {number} value */
function compact(value) {
  for (const [unit, scale] of /** @type {[string, number][]} */ ([["B", 1e9], ["M", 1e6], ["K", 1e3]])) {
    if (value >= scale) return (value / scale).toFixed(1).replace(/\.0$/, "") + unit;
  }
  return number(value);
}
/** @param {number} value */
function money(value) { return "$" + value.toFixed(value > 0 && value < 0.01 ? 4 : 2); }
/** @param {number} ms */
function duration(ms) {
  const minutes = Math.floor(ms / 60000);
  if (minutes >= 60) return Math.floor(minutes / 60) + "h " + minutes % 60 + "m";
  return minutes ? minutes + "m" : Math.floor(ms / 1000) + "s";
}
/** @param {number} count @param {number} total */
function percent(count, total) { return total ? Math.round(count / total * 100) + "%" : "0%"; }
/** @param {number} count @param {number} total */
function share(count, total) { return total > 0 ? (count / total * 100).toFixed(1) + "%" : "n/a"; }
/** @param {string} value @param {string} percentage */
function withPercentage(value, percentage) { return value + " (" + percentage + ")"; }
/** @param {UsageBucket} usage */
function savingsLabel(usage) { return withPercentage(money(usage.withoutCache - usage.cost), share(usage.withoutCache - usage.cost, usage.withoutCache)); }
/** @param {string} value */
function oneLine(value) { return value.replace(/[\x00-\x1f\x7f-\x9f]/g, " ").replace(/\s+/g, " ").trim(); }
/** @param {string} path */
function basename(path) { return path.replace(/\/+$/, "").split("/").pop() || path; }
/** @param {string} value */
function quote(value) { return "'" + value.replaceAll("'", "'\"'\"'") + "'"; }
/** @param {unknown} error */
function errorText(error) { return error instanceof Error ? error.message : String(error); }
/** @param {Date} date */
function dayKey(date) { return date.getFullYear() + "-" + String(date.getMonth() + 1).padStart(2, "0") + "-" + String(date.getDate()).padStart(2, "0"); }
/** @param {string} day */
function localDay(day) { return new Date(day + "T12:00:00"); }
/** @param {Day[]} days @param {number} period @returns {Day[]} */
function groupedDays(days, period) {
  if (!period) return days.slice().reverse();
  /** @type {Map<string, Day>} */
  const groups = new Map();
  for (const day of days) {
    const date = localDay(day.date);
    if (period === 1) date.setDate(date.getDate() - (date.getDay() + 6) % 7);
    const key = period === 1 ? dayKey(date) : day.date.slice(0, 7);
    let group = groups.get(key);
    if (!group) { group = { ...day, date: key }; groups.set(key, group); continue; }
    for (const field of /** @type {(keyof Omit<UsageBucket, "name">)[]} */ (["input", "output", "reasoning", "cache_read", "cache_write", "cost", "withoutCache", "unpriced", "unreported", "messages", "tools"])) group[field] += day[field];
  }
  return Array.from(groups.values()).reverse();
}

class UsageDashboard {
  /** @param {UiBorrow} ctx @param {string | null} workspace @param {"all" | "workspace"} scope */
  constructor(ctx, workspace, scope) {
    this.ctx = ctx;
    this.workspace = workspace;
    this.scope = scope;
    this.tab = 0;
    this.period = 0;
    this.scroll = 0;
    this.selected = 0;
    this.query = "";
    this.loading = false;
    this.closed = false;
    this.error = "";
    /** @type {Snapshot | null} */
    this.data = null;
    this.rect = { ...EMPTY_RECT };
    /** @type {Row[]} */
    this.rows = [];
    /** @type {{x: number, width: number}[]} */
    this.tabHits = [];
    /** @type {{x: number, width: number, action: () => void}[]} */
    this.controlHits = [];
    this.close = () => {};
    this.generation = 0;
  }

  async refresh() {
    const generation = ++this.generation;
    this.loading = true;
    this.error = "";
    this.ctx.tui.root.invalidatePaint();
    const home = env.get("HOME") || ".";
    const app = env.get("YUKE_APPNAME") || "yuke";
    const output = (env.get("XDG_CACHE_HOME") || home + "/.cache") + "/" + app + "/usage/snapshot-" + Date.now() + "-" + Math.random().toString(36).slice(2) + ".json";
    try {
      const config = (env.get("XDG_CONFIG_HOME") || home + "/.config") + "/" + app;
      const db = (env.get("XDG_DATA_HOME") || home + "/.local/share") + "/" + app + "/yuke.db";
      const args = ["python3", config + "/plugins/usage-data.py", db, "--output", output];
      if (this.scope === "workspace" && this.workspace) args.push("--workspace", this.workspace);
      const result = await exec(args.map(quote).join(" "), { timeoutMs: 30000, signal: this.ctx.ctx.signal });
      if (result.code !== 0) throw new Error(result.stderr.trim() || "Usage reader exited " + result.code);
      if (this.closed || generation !== this.generation) return;
      this.data = /** @type {Snapshot} */ (JSON.parse(await fs.readFile(output)));
      this.rows = [];
    } catch (error) {
      if (!this.closed && generation === this.generation) this.error = errorText(error);
    } finally {
      await fs.removeFile(output).catch(() => {});
      if (!this.closed && generation === this.generation) {
        this.loading = false;
        this.ctx.tui.root.invalidatePaint();
      }
    }
  }

  /** @returns {string} */
  scopeLabel() { return this.scope === "workspace" && this.workspace ? "Workspace · " + basename(this.workspace) : "Global · all workspaces"; }
  /** @returns {string} */
  footer() {
    if (this.rect.w < 85) return this.tab === 5 ? "1-6 tabs · / search · ↵ resume · esc close" : "1-6 tabs · g period · s scope · j/k · esc close";
    return "1-6/tab tabs · g period · s scope · r refresh · j/k scroll" + (this.tab === 5 ? " · / search · ↵ resume" : "") + " · esc close";
  }
  /** @param {number} tab */
  selectTab(tab) { this.tab = (tab + TABS.length) % TABS.length; this.scroll = 0; this.ctx.tui.root.invalidatePaint(); }
  cyclePeriod() {
    this.period = (this.period + 1) % PERIODS.length;
    this.scroll = 0;
    this.ctx.tui.root.invalidatePaint();
  }
  toggleScope() {
    if (!this.workspace) return;
    this.scope = this.scope === "all" ? "workspace" : "all";
    this.scroll = 0;
    this.selected = 0;
    this.data = null;
    void this.refresh();
  }
  /** @param {import("yuke:ui").Rect} rect */
  layout(rect) { this.rect = rect; }
  /** @param {string} value @param {string} [group] @returns {Row} */
  line(value, group = "UsageText") { return { spans: [{ x: 0, value: oneLine(value), group }] }; }
  /** @param {string} value @param {number} width @param {string} [group] @returns {Row} */
  center(value, width, group = "UsageTitle") { return { spans: [{ x: Math.max(0, Math.floor((width - measure(value)) / 2)), value, group }] }; }
  /** @param {string} label @param {string} value @param {number} width @param {string} [valueGroup] @param {string} [labelGroup] @returns {Row} */
  pair(label, value, width, valueGroup = "UsageNumber", labelGroup = "UsageDim") {
    return { spans: [{ x: 0, value: clip(label, Math.max(0, width - measure(value) - 2)), group: labelGroup }, { x: Math.max(0, width - measure(value)), value, group: valueGroup }] };
  }
  /** @param {{value: string, group: string}[]} parts @param {number} [indent] @returns {Row} */
  segments(parts, indent = 0) {
    let x = indent;
    return { spans: parts.map((part) => {
      const span = { x, ...part };
      x += measure(part.value);
      return span;
    }) };
  }
  /** @param {Row[]} left @param {Row[]} right @param {number} width @returns {Row[]} */
  columns(left, right, width) {
    if (width < 90) return [...left, this.line(""), ...right];
    const start = Math.floor(width / 2) + 2;
    return Array.from({ length: Math.max(left.length, right.length) }, (_, i) => ({ spans: [...(left[i]?.spans || []), ...(right[i]?.spans || []).map((span) => ({ ...span, x: span.x + start }))] }));
  }
  /** @param {string[][]} values @param {number[]} widths @param {string[]} [groups] @returns {Row[]} */
  table(values, widths, groups = []) {
    return values.map((cells, i) => {
      let x = 0;
      return { spans: cells.map((value, j) => {
        let group = groups[j] || (j ? "UsageNumber" : "UsageText");
        if (value.includes("+?")) group = "UsageWarning";
        if (value === "0" && (group === "UsageDanger" || group === "UsageWarning")) group = "UsageDim";
        const span = { x, value: clip(oneLine(value), Math.max(0, widths[j] - 2)), group: i === 0 ? "UsageTableHeader" : group };
        x += widths[j];
        return span;
      }) };
    });
  }
  /** @param {Snapshot} data @param {number} width @returns {Row[]} */
  heatmap(data, width) {
    const today = localDay(dayKey(new Date(data.asOf)));
    const first = new Date(today);
    first.setFullYear(first.getFullYear() - 1);
    first.setDate(first.getDate() + 1);
    const sunday = new Date(first);
    sunday.setDate(sunday.getDate() - sunday.getDay());
    const allWeeks = Math.ceil((Math.round((Date.UTC(today.getFullYear(), today.getMonth(), today.getDate()) - Date.UTC(sunday.getFullYear(), sunday.getMonth(), sunday.getDate())) / 86400000) + 1) / 7);
    const spacing = width >= allWeeks * 2 + 4 ? 2 : 1;
    const weeks = Math.min(allWeeks, Math.max(1, Math.floor((width - 4) / spacing)));
    const start = new Date(sunday);
    start.setDate(start.getDate() + (allWeeks - weeks) * 7);
    const counts = new Map(data.daily.map((day) => [day.date, day.input + day.output]));
    const peak = Math.max(1, ...data.daily.filter((day) => day.date >= dayKey(first) && day.date <= dayKey(today)).map((day) => day.input + day.output));
    const rows = [this.line("Token activity", "UsageTitle"), this.line(weeks === allWeeks ? "Last 12 months" : "Recent " + weeks + " weeks (resize for 12 months)", "UsageDim"), this.line("")];
    /** @type {Row} */
    const labels = { spans: [] };
    let lastMonth = -1;
    let lastLabelX = -10;
    for (let week = 0; week < weeks; week++) {
      const date = new Date(start);
      date.setDate(date.getDate() + week * 7);
      if (date.getMonth() !== lastMonth && 4 + week * spacing >= lastLabelX + 4) {
        labels.spans.push({ x: 4 + week * spacing, value: MONTHS[date.getMonth()], group: "UsageDim" });
        lastLabelX = 4 + week * spacing;
      }
      lastMonth = date.getMonth();
    }
    rows.push(labels);
    for (let weekday = 0; weekday < 7; weekday++) {
      const row = this.line(["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"][weekday], "UsageDim");
      for (let week = 0; week < weeks; week++) {
        const date = new Date(start);
        date.setDate(date.getDate() + week * 7 + weekday);
        if (date < first || date > today) continue;
        const count = counts.get(dayKey(date)) || 0;
        const level = count ? Math.min(4, Math.max(1, Math.ceil(count / peak * 4))) : 0;
        row.spans.push({ x: 4 + week * spacing, value: "▪", group: "UsageHeat" + level });
      }
      rows.push(row);
    }
    rows.push(this.line(""), { spans: [{ x: 2, value: "Less", group: "UsageDim" }, ...[0, 1, 2, 3, 4].map((level) => ({ x: 8 + level * 2, value: "▪", group: "UsageHeat" + level })), { x: 19, value: "More", group: "UsageDim" }] });
    return rows;
  }
  /** @param {Snapshot} data @param {number} width @returns {Row[]} */
  overview(data, width) {
    const total = data.totals;
    const peak = Math.max(0, ...data.daily.map((day) => day.input + day.output));
    const rows = Array.from({ length: this.rect.h >= 40 ? 6 : 1 }, () => this.line(""));
    rows.push(this.center("Yuke", width), this.center(this.scopeLabel(), width, "UsageDim"), this.center(countLabel(data.chatCount, "chat") + " · " + countLabel(data.childCount, "child session"), width, "UsageDim"), this.line(""));
    const metrics = [[compact(total.input + total.output), "Lifetime tokens", "UsageNumber"], [compact(peak), "Peak daily tokens", "UsageNumber"], [duration(data.longestChatMs), "Longest chat", "UsageReasoning"], [countLabel(data.currentStreak, "day"), "Current streak", "UsageGood"], [countLabel(data.longestStreak, "day"), "Longest streak", "UsageGood"]];
    if (width >= 85) {
      for (let row = 0; row < 2; row++) rows.push({ spans: metrics.map((metric, i) => ({ x: Math.max(0, Math.floor(width / 5 * i + (width / 5 - measure(metric[row])) / 2)), value: metric[row], group: row ? "UsageDim" : metric[2] })) });
    } else {
      for (const metric of metrics) rows.push(this.pair(metric[1], metric[0], width, metric[2]));
    }
    rows.push(this.line(""), ...this.heatmap(data, width), this.line(""));
    const colWidth = width >= 90 ? Math.floor(width / 2) - 3 : width;
    const effort = data.efforts[0];
    const left = [this.line("Activity insights", "UsageTitle"), this.line(""),
      this.pair("Known API cost", money(total.cost) + (total.unpriced ? " + unpriced" : ""), colWidth, "UsageCost"),
      this.pair("Cache savings", savingsLabel(total), colWidth, "UsageGood"),
      this.pair("Cache reads (% of input)", share(total.cache_read, total.input), colWidth, "UsageGood"),
      this.pair("Most used reasoning", effort ? withPercentage(effort.name, percent(effort.count, total.messages)) : "No activity", colWidth, "UsageReasoning"),
      this.pair("Skills explored", number(data.skills.length), colWidth),
      this.pair("Total skill uses", number(data.skills.reduce((sum, skill) => sum + skill.uses, 0)), colWidth),
      this.pair("Tool calls", number(total.tools), colWidth)];
    const top = [...data.skills.map((skill) => ({ name: "$" + skill.name, count: skill.uses })), ...data.tools.map((tool) => ({ name: tool.name, count: tool.calls }))].sort((a, b) => b.count - a.count).slice(0, 6);
    const right = [this.line("Most used tools and skills", "UsageTitle"), this.line(""), ...top.map((item) => this.pair(item.name, countLabel(item.count, "use"), colWidth, "UsageNumber", item.name.startsWith("$") ? "UsageReasoning" : "UsageTool"))];
    rows.push(...this.columns(left, right, width), this.line(""), this.line("Statistics as of " + new Date(data.asOf).toLocaleString() + " · local timezone", "UsageDim"));
    if (!total.messages) rows.push(this.line("No recorded model activity yet.", "UsageDim"));
    return rows;
  }
  /** @param {UsageBucket[]} buckets @param {number} width @returns {Row[]} */
  usageTable(buckets, width) {
    const narrow = width < 100;
    const fixed = narrow ? [12, 12, 13] : [12, 12, 18, 10, 13];
    return this.table([
      narrow ? ["Name", "Tokens", "Replies", "Known cost"] : ["Name", "Input", "Output", "Cache read", "Replies", "Known cost"],
      ...buckets.map((item) => narrow ? [item.name, compact(item.input + item.output), number(item.messages), money(item.cost) + (item.unpriced ? "+?" : "")] : [item.name, compact(item.input), compact(item.output), withPercentage(compact(item.cache_read), share(item.cache_read, item.input)), number(item.messages), money(item.cost) + (item.unpriced ? "+?" : "")]),
    ], [Math.max(12, width - fixed.reduce((sum, item) => sum + item, 0)), ...fixed], narrow ? ["UsageText", "UsageNumber", "UsageNumber", "UsageCost"] : ["UsageText", "UsageNumber", "UsageNumber", "UsageGood", "UsageNumber", "UsageCost"]);
  }
  /** @param {Snapshot} data @param {number} width @returns {Row[]} */
  usage(data, width) {
    const t = data.totals;
    const total = t.input + t.output;
    const uncached = Math.max(0, t.input - t.cache_read - t.cache_write);
    const rows = [this.line("Token breakdown", "UsageTitle"), this.line("Input includes cached tokens. Output includes reasoning tokens.", "UsageDim"), this.line(""), this.pair("Total tokens", number(total), width)];
    for (const [label, value, basis, group] of [
      ["Input (% of total)", t.input, total, "UsageNumber"],
      ["Output (% of total)", t.output, total, "UsageNumber"],
      ["Reasoning (% of output)", t.reasoning, t.output, "UsageReasoning"],
      ["Cache reads (% of input)", t.cache_read, t.input, "UsageGood"],
      ["Cache writes (% of input)", t.cache_write, t.input, "UsageGood"],
      ["Uncached input (% of input)", uncached, t.input, "UsageNumber"],
    ]) rows.push(this.pair(String(label), withPercentage(number(Number(value)), share(Number(value), Number(basis))), width, String(group)));
    rows.push(this.pair("Known API cost (% of no-cache)", withPercentage(money(t.cost), share(t.cost, t.withoutCache)), width, "UsageCost"), this.pair("Without caching, at recorded prices", money(t.withoutCache), width, "UsageCost"), this.pair("Cache savings (% of no-cache)", savingsLabel(t), width, "UsageGood"), this.pair("Replies with unknown prices", number(t.unpriced), width, t.unpriced ? "UsageWarning" : "UsageDim"), this.pair("Replies without token counts", number(t.unreported), width, t.unreported ? "UsageWarning" : "UsageDim"), this.line("Cost % uses the no-cache estimate for priced replies, not subscription charges.", "UsageDim"), this.line("Cache read % is the share of input reused from cache.", "UsageDim"), this.line(""), this.line("Usage by provider", "UsageTitle"), ...this.usageTable(data.providers, width), this.line(""), this.line("Usage by model", "UsageTitle"), ...this.usageTable(data.models, width), this.line(""), this.line(PERIODS[this.period] + " usage" + (this.period === 1 ? " · weeks start Monday" : ""), "UsageTitle"), ...this.usageTable(groupedDays(data.daily, this.period).map((day) => ({ ...day, name: day.date })), width));
    return rows;
  }
  /** @param {Snapshot} data @param {number} width @returns {Row[]} */
  messages(data, width) {
    const total = Object.values(data.roles).reduce((sum, count) => sum + count, 0);
    const rows = [this.line("Message activity", "UsageTitle"), this.line("Recorded messages, including child sessions and compactions.", "UsageDim"), this.line(""), this.pair("Total messages", number(total), width)];
    for (const [role, label] of [["user", "User messages"], ["assistant", "Assistant replies"], ["engine", "Engine-generated inputs"], ["compaction", "Compaction summaries"]]) rows.push(this.pair(label, number(data.roles[role] || 0), width));
    rows.push(this.pair("Average output per counted reply", compact(data.totals.output / Math.max(1, data.totals.messages - data.totals.unreported)) + " tokens", width), this.pair("Completed runs", number(data.completedRuns), width), this.pair("Summed run time (children included)", duration(data.activeMs), width), this.line(""), this.line("Reply finish reasons", "UsageTitle"));
    for (const [name, count] of Object.entries(data.finishes).sort((a, b) => b[1] - a[1])) rows.push(this.pair(name, withPercentage(number(count), percent(count, data.totals.messages)), width, ["error", "content_filter", "refusal"].includes(name) ? "UsageDanger" : name === "canceled" ? "UsageWarning" : "UsageGood"));
    rows.push(this.line(""), this.line("Run outcomes", "UsageTitle"));
    for (const [name, count] of Object.entries(data.outcomes).sort((a, b) => b[1] - a[1])) rows.push(this.pair(name, number(count), width, name === "failed" ? "UsageDanger" : name === "canceled" ? "UsageWarning" : "UsageGood"));
    rows.push(this.line(""), this.line("Reasoning effort by reply", "UsageTitle"));
    for (const effort of data.efforts) rows.push(this.pair(effort.name, withPercentage(number(effort.count), percent(effort.count, data.totals.messages)), width, "UsageReasoning"));
    return rows;
  }
  /** @param {Snapshot} data @param {number} width @returns {Row[]} */
  pluginStats(data, width) {
    const rows = [this.line("Loaded plugins · this Yuke process", "UsageTitle"), this.line("Yuke does not record historical plugin run counts.", "UsageDim"), this.line("")];
    for (const name of this.ctx.ctx.inspectPlugins().filter(item => !item.closing).map(item => item.name).sort()) rows.push(this.pair(name, "● loaded", width, "UsageGood", "UsageText"));
    rows.push(this.line(""), this.line("Tool activity · " + this.scopeLabel(), "UsageTitle"), this.line("Counts include successful, failed, and canceled committed calls.", "UsageDim"), this.line(""), ...this.table([["Tool", "Calls", "Errors", "Canceled", "Run time"], ...data.tools.map((tool) => [tool.name, number(tool.calls), number(tool.errors), number(tool.canceled), duration(tool.durationMs)])], [Math.max(12, width - 44), 11, 11, 11, 11], ["UsageTool", "UsageNumber", "UsageDanger", "UsageWarning", "UsageDim"]));
    return rows;
  }
  /** @param {Snapshot} data @param {number} width @returns {Row[]} */
  skillStats(data, width) {
    const rows = [this.line("Skill activity", "UsageTitle"), this.line("Observed uses: invocations and known skill-file reads, once per skill per run.", "UsageDim"), this.line(""), this.pair("Skills explored", number(data.skills.length), width), this.pair("Skills in stored catalogs", number(data.catalogSkills), width), this.pair("Observed skill uses", number(data.skills.reduce((sum, item) => sum + item.uses, 0)), width), this.line(""), ...this.table([["Skill", "Uses", "Invocations", "File reads"], ...data.skills.map((skill) => ["$" + skill.name, number(skill.uses), number(skill.invocations), number(skill.reads)])], [Math.max(12, width - 40), 10, 15, 15], ["UsageReasoning", "UsageNumber", "UsageNumber", "UsageNumber"])];
    if (!data.skills.length) rows.push(this.line("No recorded skill invocations or known skill-file reads.", "UsageDim"));
    return rows;
  }
  /** @returns {Chat[]} */
  chats() {
    const query = this.query.toLowerCase();
    return (this.data?.chats || []).filter((chat) => !query || [chat.title, chat.root, chat.model, chat.id, chat.kind].join(" ").toLowerCase().includes(query));
  }
  /** @param {number} width @returns {Row[]} */
  chatStats(width) {
    const chats = this.chats();
    this.selected = Math.max(0, Math.min(this.selected, chats.length - 1));
    const rows = [this.line("Chats · newest first", "UsageTitle"), this.line("Longest chat uses first-to-last message time, including idle gaps.", "UsageDim"), this.line(this.query ? "Search: " + this.query : "Press / to filter by title, workspace, model, or id.", "UsageDim"), this.line("")];
    if (!chats.length) rows.push(this.line("No matching chats.", "UsageDim"));
    for (let i = 0; i < chats.length; i++) {
      const chat = chats[i];
      const selected = i === this.selected;
      const badge = chat.kind === "child" ? " [child]" : chat.kind === "fork" ? " [fork]" : "";
      const title = clip((selected ? "› " : "  ") + oneLine(chat.title), Math.max(0, width - measure(badge)));
      rows.push({ ...this.segments([{ value: title, group: selected ? "UsageSelected" : "UsageChatTitle" }, { value: badge, group: "UsageReasoning" }]), chat });
      rows.push(this.segments([
        { value: basename(chat.root), group: "UsageDim" },
        { value: " · ", group: "UsageDim" },
        { value: chat.model, group: "UsageReasoning" },
        { value: " · " + number(chat.messages) + " msgs · ", group: "UsageDim" },
        { value: compact(chat.input + chat.output) + " tokens", group: "UsageNumber" },
        { value: " · ", group: "UsageDim" },
        { value: money(chat.cost) + (chat.unpriced ? "+?" : ""), group: chat.unpriced ? "UsageWarning" : "UsageCost" },
      ], 2));
      rows.push(this.line("  " + new Date(chat.updated).toLocaleDateString() + " · elapsed " + duration(chat.elapsedMs) + " · run time " + duration(chat.activeMs), "UsageDim"), this.line(""));
    }
    return rows;
  }
  /** @param {number} width @returns {Row[]} */
  buildRows(width) {
    if (this.error) return [this.line("Cannot load usage", "UsageDanger"), this.line(this.error, "UsageWarning"), this.line("Press r to retry, or esc to close.", "UsageDim")];
    const data = this.data;
    if (!data) return [this.line("Reading local usage history…", "UsageDim")];
    let rows;
    switch (this.tab) {
      case 0: rows = this.overview(data, width); break;
      case 1: rows = this.usage(data, width); break;
      case 2: rows = this.messages(data, width); break;
      case 3: rows = this.pluginStats(data, width); break;
      case 4: rows = this.skillStats(data, width); break;
      default: rows = this.chatStats(width);
    }
    if (data.notes.length || data.totals.unreported || data.totals.unpriced) rows.push(this.line(""), ...data.notes.map((note) => this.line(note, "UsageWarning")));
    if (data.totals.unreported) rows.push(this.line(countLabel(data.totals.unreported, "reply", "replies") + " omitted token counts; token totals are partial.", "UsageWarning"));
    if (data.totals.unpriced) rows.push(this.line(countLabel(data.totals.unpriced, "reply", "replies") + (data.totals.unpriced === 1 ? " has" : " have") + " unknown prices; cost totals are partial.", "UsageWarning"));
    return rows;
  }
  draw() {
    const r = this.rect;
    text(r.x, r.y, clip("Usage · Yuke · " + this.scopeLabel() + (this.loading ? " · refreshing…" : ""), r.w), "UsageTitle");
    let x = 0;
    this.tabHits = [];
    for (let i = 0; i < TABS.length; i++) {
      const label = r.w < 50 ? TABS[i].slice(0, 1) : r.w < 78 ? TABS[i].slice(0, 3) : TABS[i];
      const value = " " + (i + 1) + " " + label + " ";
      const width = measure(value);
      this.tabHits.push({ x, width });
      if (x < r.w) text(r.x + x, r.y + 1, clip(value, r.w - x), this.tab === i ? "UsageActiveTab" : "UsageDim");
      x += width + 1;
    }
    text(r.x, r.y + 2, "─".repeat(r.w), "UsageRule");
    x = 0;
    this.controlHits = [];
    const controls = [
      { value: "g " + PERIODS[this.period], action: () => this.cyclePeriod() },
      { value: "s " + (this.scope === "all" ? "Global" : "Workspace"), action: () => this.toggleScope() },
      { value: "r Refresh", action: () => { void this.refresh(); } },
    ];
    for (const control of controls) {
      const width = measure(control.value);
      this.controlHits.push({ x, width, action: control.action });
      if (x < r.w) text(r.x + x, r.y + 3, clip(control.value.slice(0, 1), r.w - x), "UsageShortcut");
      if (x + 1 < r.w) text(r.x + x + 1, r.y + 3, clip(control.value.slice(1), r.w - x - 1), "UsageText");
      x += width + 3;
    }
    if (this.workspace && this.scope === "workspace" && x < r.w) text(r.x + x, r.y + 3, clip(this.workspace, r.w - x), "UsageDim");
    const margin = r.w >= 120 ? Math.floor(r.w * 0.08) : 1;
    const width = Math.max(1, r.w - margin * 2);
    const height = Math.max(0, r.h - 5);
    this.rows = this.buildRows(width);
    this.scroll = Math.max(0, Math.min(this.scroll, this.rows.length - height));
    for (let i = 0; i < height; i++) {
      const row = this.rows[i + this.scroll];
      if (!row) break;
      for (const span of row.spans) {
        if (span.x >= width) continue;
        text(r.x + margin + span.x, r.y + 5 + i, clip(span.value, width - span.x), span.group);
      }
    }
    if (this.rows.length > height && r.h > 5) text(r.x + r.w - 1, r.y + 5 + Math.floor(this.scroll / Math.max(1, this.rows.length - height) * Math.max(0, height - 1)), "┃", "UsageDim");
  }
  /** @param {number} delta */
  move(delta) {
    if (this.tab === 5) {
      this.selected = Math.max(0, Math.min(this.selected + delta, this.chats().length - 1));
      const row = 4 + this.selected * 4;
      const height = Math.max(1, this.rect.h - 5);
      if (row < this.scroll) this.scroll = row;
      if (row + 2 >= this.scroll + height) this.scroll = row + 3 - height;
    } else this.scroll += delta;
    this.ctx.tui.root.invalidatePaint();
  }
  async search() {
    const query = await this.ctx.ctx.interaction.input("Filter chats", "Title, workspace, model, or id; blank clears the filter");
    if (query === undefined || this.closed) return;
    this.query = query;
    this.selected = this.scroll = 0;
    this.ctx.tui.root.invalidatePaint();
  }
  resume() {
    const chat = this.chats()[this.selected];
    const pane = currentPane();
    if (!chat || !pane) return;
    this.close();
    showSession(pane, chat.id);
  }
  /** @param {Parameters<Window["onKey"]>[0]} event @returns {boolean} */
  onKey(event) {
    if (event.type !== "key" || event.event === "release") return true;
    const stroke = keys.strokeOf(event);
    if (/^[1-6]$/.test(stroke)) this.selectTab(Number(stroke) - 1);
    else if (["tab", "right", "l"].includes(stroke)) this.selectTab(this.tab + 1);
    else if (["shift+tab", "left", "h"].includes(stroke)) this.selectTab(this.tab - 1);
    else if (stroke === "g") this.cyclePeriod();
    else if (stroke === "s") this.toggleScope();
    else if (stroke === "r") void this.refresh();
    else if (["down", "j", "ctrl+n"].includes(stroke)) this.move(1);
    else if (["up", "k", "ctrl+p"].includes(stroke)) this.move(-1);
    else if (["pagedown", "ctrl+d", "pageup", "ctrl+u"].includes(stroke)) this.move((stroke === "pageup" || stroke === "ctrl+u" ? -1 : 1) * Math.max(1, this.rect.h - 8));
    else if (stroke === "home") { this.selected = this.scroll = 0; this.ctx.tui.root.invalidatePaint(); }
    else if (stroke === "end") { this.selected = Math.max(0, this.chats().length - 1); this.scroll = this.rows.length; this.ctx.tui.root.invalidatePaint(); }
    else if (stroke === "/" && this.tab === 5) void this.search();
    else if (stroke === "enter" && this.tab === 5) this.resume();
    else if (["esc", "ctrl+c", "q"].includes(stroke)) this.close();
    return true;
  }
  /** @param {Parameters<Window["onMouse"]>[0]} event @returns {boolean} */
  onMouse(event) {
    if (event.event !== "press") return true;
    if (event.button === "wheel_up" || event.button === "wheel_down") { this.move((event.button === "wheel_up" ? -3 : 3) * (event.count || 1)); return true; }
    if (event.button !== "left") return true;
    const x = event.col - this.rect.x;
    const y = event.row - this.rect.y;
    if (y === 1) {
      const tab = this.tabHits.findIndex((hit) => x >= hit.x && x < hit.x + hit.width);
      if (tab >= 0) this.selectTab(tab);
    } else if (y === 3) {
      this.controlHits.find((hit) => x >= hit.x && x < hit.x + hit.width)?.action();
    } else if (this.tab === 5 && y >= 5) {
      const chat = this.rows[y - 5 + this.scroll]?.chat;
      if (chat) { this.selected = this.chats().findIndex((item) => item.id === chat.id); this.ctx.tui.root.invalidatePaint(); if (event.count >= 2) this.resume(); }
    }
    return true;
  }
}
/** Register historical usage inspection. The plugin owns registrations; host failures throw. @param {import("yuke").Context} parent */
export default function(parent) {

    {
const tuiBorrow = parent.get("tui");
if (tuiBorrow) {
const c = { ctx: parent, tui: tuiBorrow };

      c.tui.style.set({
        UsageText: { link: "UIPanel", fg: "fg" },
        UsageDim: { link: "UIPanel", fg: "muted", dim: false },
        UsageTitle: { link: "UIPanel", fg: "accent", bold: true },
        UsageTableHeader: { link: "UsageTitle", underline: true },
        UsageNumber: { link: "UIPanel", fg: "cyan", bold: true },
        UsageTool: { link: "UIPanel", fg: "cyan" },
        UsageReasoning: { link: "UIPanel", fg: "violet" },
        UsageCost: { link: "UIPanel", fg: "yellow" },
        UsageGood: { link: "UIPanel", fg: "green" },
        UsageWarning: { link: "UIPanel", fg: "warn" },
        UsageDanger: { link: "UIPanel", fg: "danger", bold: true },
        UsageChatTitle: { link: "UIPanel", fg: "strongFg", bold: true },
        UsageSelected: { link: "UsageChatTitle", bg: "userBg" },
        UsageActiveTab: { link: "UIPanel", fg: "bg", bg: "accent", bold: true },
        UsageShortcut: { link: "UsageTitle" },
        UsageRule: { link: "UIPanel", fg: "accent" },
      });
      let releaseHeat = () => {};
      const applyHeat = () => {
        releaseHeat();
        const dark = c.tui.background === "dark";
        const colors = c.tui.colors === "truecolor"
          ? dark ? ["#1b4047", "#415853", "#6d7863", "#afb28b", "#ffe3ac"] : ["#dedaca", "#b8b697", "#93906c", "#776d3a", "#59490b"]
          : dark ? [237, 239, 243, 144, 223] : [187, 144, 101, 100, 58];
        releaseHeat = c.tui.style.set(Object.fromEntries(colors.map((fg, level) => ["UsageHeat" + level, { link: "UIPanel", fg, dim: false }])));
      };
      applyHeat();
      c.ctx.on("background.changed", applyHeat);

      c.ctx.own(() => releaseHeat());
      /** @type {UsageDashboard | null} */
      let dashboard = null;
      c.ctx.own(() => { if (dashboard) { dashboard.closed = true; dashboard.close(); } });
      c.tui.command.add("usage", {
        desc: "view global or workspace usage, costs, tools, skills, and chats",
        slash: true,
        args: true,
        run: async (arg = "") => {
          if (dashboard && !dashboard.closed) return;
          const requested = typeof arg === "string" ? arg.trim() : "";
          if (requested && !["all", "global", "current", "workspace"].includes(requested)) { c.ctx.interaction.notify("Usage: /usage [global | current]", "info"); return; }
          const workspace = currentEntry()?.session.root || (await fs.stat("."))?.path || null;
          if (!c.ctx.alive) return;
          dashboard = new UsageDashboard(c, workspace, requested === "current" || requested === "workspace" ? "workspace" : "all");
          const view = dashboard;
          const win = new Window({ border: "none", width: (max) => max, height: (max) => max, content: view, footer: () => view.footer(), outsidePress: "ignore" });
          view.close = c.tui.overlay(win, () => { view.closed = true; });
          void view.refresh();
        },
      });
}
}

}
