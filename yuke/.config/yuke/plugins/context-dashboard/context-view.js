/** @import { UiBorrow } from "../../types.js" */
//! A cold, read-only context inspection. Drawing reads cached rows only.
import { client, env, exec } from "yuke";
import { currentPane } from "yuke:session";
import { Window, clip, keys, measure, text } from "yuke:ui";
import { breakdown, squares } from "./context-model.js";
/** @import { Context, ToolInspection } from "yuke" */
/** @import { Snapshot } from "./context-model.js" */
/** @typedef {{ x: number, value: string, group: string }} Span */
/** @typedef {{ spans: Span[] }} Row */

const TABS = ["Overview", "Details", "Skills", "Tools"];
/** @param {number} value */
function number(value) { return String(Math.round(value)).replace(/\B(?=(\d{3})+(?!\d))/g, ","); }
/** @param {string} value */
function clean(value) { return value.replace(/[\x00-\x1f\x7f-\x9f]/g, " "); }
/** @param {string} value */
function quote(value) { return "'" + value.replaceAll("'", "'\\''") + "'"; }

class ContextDashboard {
  /** @param {UiBorrow} ctx @param {ReturnType<import("yuke").Context["resources"]>} owner @param {string | null} sessionId @param {string} model */
  constructor(ctx, owner, sessionId, model) {
    this.ctx = ctx;
    this.owner = owner;
    this.sessionId = sessionId;
    this.model = model;
    this.used = 0;
    this.window = 0;
    this.tab = 0;
    this.promptGrid = false;
    this.scroll = 0;
    this.loading = false;
    this.closed = false;
    this.error = "";
    this.rect = { x: 0, y: 0, w: 0, h: 0 };
    /** @type {Snapshot | null} */
    this.saved = null;
    /** @type {Wire.SessionListItem | null} */
    this.item = null;
    /** @type {Row[]} */
    this.rows = [];
    /** @type {ToolInspection[] | null} */
    this.tools = null;
    this.footer = "1-4 tabs · v grid scale · r refresh · j/k scroll · esc close";
    this.close = () => {};
    this.pending = Promise.resolve();
  }

  refresh() {
    if (this.loading || this.closed) return;
    this.loading = true;
    this.error = "";
    this.rebuild();
    this.pending = this.read().catch(error => {
      if (!this.closed) this.error = error instanceof Error ? error.message : String(error);
    }).finally(() => {
      if (!this.closed) { this.loading = false; this.rebuild(); }
    });
  }

  async read() {
    const item = this.sessionId ? await client.sessionContextInfo(this.sessionId) : null;
    const catalog = await client.catalogList(null);
    let saved = null;
    if (this.sessionId) {
      const home = env.get("HOME") || ".";
      const app = env.get("YUKE_APPNAME") || "yuke";
      const config = (env.get("XDG_CONFIG_HOME") || home + "/.config") + "/" + app;
      const database = (env.get("XDG_DATA_HOME") || home + "/.local/share") + "/" + app + "/yuke.db";
      let output = "";
      const result = await exec(["python3", config + "/plugins/context-data.py", database, this.sessionId].map(quote).join(" "), {
        signal: this.owner.signal, timeoutMs: 15000, onOutput: chunk => { output += chunk; },
      });
      if (result.code !== 0) throw new Error(result.stderr.trim() || "Context reader failed.");
      saved = /** @type {Snapshot} */ (JSON.parse(output));
      if (saved.model !== (item?.activity.config?.model || item?.session.model)) { saved.valid = false; saved.promptAvailable = false; }
    }
    if (this.closed) return;
    this.tools = typeof this.ctx.ctx.tools.inspect === "function" ? this.ctx.ctx.tools.inspect().sort((a, b) => b.estimatedBytes - a.estimatedBytes || a.name.localeCompare(b.name)) : null;
    this.item = item;
    this.saved = saved;
    this.model = item?.activity.config?.model || item?.session.model || this.model;
    this.used = item?.activity.context_tokens || 0;
    this.window = catalog.type === "full" ? catalog.models.find(model => model.selector === this.model)?.context_window || 0 : 0;
  }

  /** @param {import("yuke:ui").Rect} rect */
  layout(rect) {
    const changed = rect.w !== this.rect.w || rect.h !== this.rect.h;
    this.rect = rect;
    if (changed) this.rebuild();
  }

  /** @param {string} value @param {string} [group] @returns {Row} */
  line(value, group = "ContextText") { return { spans: [{ x: 0, value: clip(clean(value), Math.max(0, this.rect.w - 2)), group }] }; }
  /** @param {string} label @param {string} value @param {string} [group] @param {number} [width] @returns {Row} */
  pair(label, value, group = "ContextText", width = Math.max(0, this.rect.w - 2)) {
    const shown = clip(clean(value), Math.floor(width * 0.57));
    const x = Math.max(0, width - measure(shown));
    return { spans: [{ x: 0, value: clip(clean(label), Math.max(0, x - 2)), group }, { x, value: shown, group }] };
  }

  /** @param {number} tokens @param {number} bytes */
  cost(tokens, bytes) {
    return "≈" + number(tokens) + " tok · " + number(bytes) + " B" + (this.used ? " · " + (tokens / this.used * 100).toFixed(2) + "% ctx" : "");
  }

  rebuild() {
    const rows = [this.line("Context · " + (this.sessionId ? "current chat" : "new chat"), "ContextTitle"), this.line(this.model || "No model selected", "ContextDim")];
    let x = 0;
    const tabs = { spans: /** @type {Span[]} */ ([]) };
    for (let i = 0; i < TABS.length; i++) {
      const value = " " + (i + 1) + " " + TABS[i] + " ";
      tabs.spans.push({ x, value: clip(value, Math.max(0, this.rect.w - 2 - x)), group: this.tab === i ? "ContextActiveTab" : "ContextDim" });
      x += measure(value) + 1;
    }
    rows.push(tabs, this.line("─".repeat(Math.max(0, this.rect.w - 2)), "ContextDim"));
    if (this.loading) rows.push(this.line("Reading context…", "ContextDim"));
    else if (this.error) rows.push(this.line("Cannot read context", "ContextWarning"), this.line(this.error), this.line("Press r to retry.", "ContextDim"));
    else {
      const budget = breakdown(this.used, this.window, this.saved);
      if (!this.tab) {
        rows.push(this.pair("Occupied context", number(this.used) + (this.window ? " / " + number(this.window) + " · " + (this.used / this.window * 100).toFixed(1) + "%" : " · window unknown"), "ContextTitle"));
        const width = Math.max(0, this.rect.w - 2);
        const split = this.window > 0 && width >= 96;
        const gridWidth = split ? Math.floor(width * 0.4) : width;
        const legendX = split ? gridWidth + 4 : 0;
        const legendWidth = width - legendX;
        const zoom = this.promptGrid && budget.promptAttributed;
        const gridNote = this.window > 0 ? this.line(zoom ? "Each square ≈ 0.5% of the saved prompt budget; v shows the window." : this.used > this.window ? "Each square ≈ 0.5% of oversized context; shares round." : "Each square ≈ 0.5% of the window; v zooms into the prompt.", "ContextDim") : null;
        /** @type {Row[]} */
        const gridRows = [];
        const legendRows = [this.line("Context breakdown", "ContextTitle")];
        rows.push(this.line(""));
        if (this.window > 0) {
          const categories = zoom ? budget.categories.filter(category => ["ContextSystem", "ContextInstructions", "ContextSkills", "ContextTools"].includes(category.group)) : budget.categories;
          const cells = squares(categories, 200);
          const columns = Math.max(1, Math.floor(gridWidth / 2));
          gridRows.push(this.line("Context grid", "ContextTitle"));
          for (let start = 0; start < cells.length; start += columns) {
            const row = { spans: /** @type {Span[]} */ ([]) };
            for (let i = 0; i < columns && start + i < cells.length; i++) row.spans.push({ x: i * 2 + 1, value: cells[start + i].glyph, group: cells[start + i].group });
            gridRows.push(row);
          }
        }
        for (let i = 0; i < budget.categories.length; i++) {
          const category = budget.categories[i];
          legendRows.push(this.pair(category.glyph + " " + category.label, (category.group === "ContextTools" && !budget.attributed ? "Unknown" : "≈" + number(category.tokens)) + (this.window && (category.group !== "ContextTools" || budget.attributed) ? " · " + (category.tokens / this.window * 100).toFixed(1) + "%" : ""), category.group, legendWidth));
        }
        if (split) {
          for (let i = 0; i < Math.max(gridRows.length, legendRows.length); i++) {
            const row = gridRows[i] || { spans: [] };
            if (i < legendRows.length) {
              const spans = legendRows[i].spans;
              for (let n = 0; n < spans.length; n++) { spans[n].x += legendX; row.spans.push(spans[n]); }
            }
            rows.push(row);
          }
        } else {
          for (let i = 0; i < gridRows.length; i++) rows.push(gridRows[i]);
          if (gridNote) rows.push(gridNote, this.line(""));
          for (let i = 0; i < legendRows.length; i++) rows.push(legendRows[i]);
        }
        if (this.window > 0) {
          if (split && gridNote) rows.push(gridNote);
          if (this.used > this.window) rows.push(this.line("Over window by " + number(this.used - this.window) + " tokens; grid is full.", "ContextWarning"));
        }
        rows.push(this.line(""), this.line("Total: provider count + estimates of later messages.", "ContextDim"));
        if (budget.attributed) rows.push(this.line("Split: estimates at 4 UTF-8 bytes per token, not provider attribution.", "ContextDim"), this.line("Tools include request overrides; chat is the remaining context.", "ContextDim"));
        else if (budget.promptAttributed) rows.push(this.line("Saved prompt estimates; tools remain in unattributed chat.", "ContextWarning"));
        else rows.push(this.line(this.sessionId ? "No valid request breakdown. A new turn can rebuild it." : "No saved request yet. Send a message to inspect its breakdown.", "ContextWarning"));
        if (this.saved?.stale) rows.push(this.line("Reload changed the next prompt. These are saved section sizes.", "ContextWarning"));
        rows.push(this.line("Cached input still occupies context. Skill bodies live in chat.", "ContextDim"));
      } else if (this.tab === 1) {
        rows.push(this.line("Request budget", "ContextTitle"), this.pair("Model window", this.window ? number(this.window) : "Unknown"), this.pair("Auto-compaction threshold", this.window ? number(budget.compactAt) : "Unknown"), this.pair("Safety reserve", this.window ? number(budget.reserve) : "Unknown", "ContextReserve"));
        if (this.item) {
          const usage = this.item.usage_last;
          rows.push(this.pair("Messages / queued", number(this.item.session.message_count) + " / " + number(this.item.activity.queued)), this.pair("Compaction", this.item.activity.pending_compaction ? "Pending" : "None"));
          if (usage) rows.push(this.pair("Last reported input", number(usage.input)), this.pair("Last cache read / write", number(usage.cache_read) + " / " + number(usage.cache_write)), this.pair("Last output / reasoning", number(usage.output) + " / " + number(usage.reasoning)));
          const total = this.item.session.usage_total;
          const cost = this.item.session.cost;
          rows.push(this.pair("Session input / output", number(total.input) + " / " + number(total.output)), this.pair("Session reasoning", number(total.reasoning)), this.pair("Known API cost", "$" + cost.total.toFixed(3) + (cost.unpriced ? " + " + number(cost.unpriced) + " unpriced" : "")));
        }
        rows.push(this.line(""), this.line("Saved prompt sections · estimates", "ContextTitle"));
        if (this.saved) {
          for (const section of this.saved.sections) rows.push(this.pair(section.key, this.cost(section.tokens, section.bytes), section.key === "skills" ? "ContextSkills" : section.key === "instructions" ? "ContextInstructions" : "ContextSystem"));
          rows.push(this.line(""), this.line("Instruction sources", "ContextTitle"));
          for (const source of this.saved.sources) rows.push(this.line(source.scope + " · " + source.path, "ContextInstructions"));
          rows.push(this.line(""), this.line("Skill catalog · " + this.saved.skills.length + " summaries, not bodies", "ContextTitle"));
          for (const skill of this.saved.skills) rows.push(this.pair(skill.name, skill.tokens == null || skill.bytes == null ? "Summary size unavailable" : this.cost(skill.tokens, skill.bytes), "ContextSkills"));
          if (!this.saved.valid) rows.push(this.line("Saved prompt is stale or its request budget is unavailable.", "ContextWarning"));
        } else rows.push(this.line("No saved prompt.", "ContextDim"));
      } else if (this.tab === 2) {
        rows.push(this.line("Per-skill summary cost · estimates", "ContextTitle"), this.line("Includes name, description, path, and XML markup.", "ContextDim"), this.line("% ctx uses occupied context, not the full model window.", "ContextDim"), this.line("Loaded bodies and read results stay in chat; this table excludes them.", "ContextDim"), this.line(""));
        if (this.saved) {
          for (const skill of this.saved.skills) rows.push(this.pair(skill.name, skill.tokens == null || skill.bytes == null ? "Not measured in saved catalog" : this.cost(skill.tokens, skill.bytes), "ContextSkills"));
          if (this.saved.skillOverhead) rows.push(this.pair("Catalog header / separators", this.cost(this.saved.skillOverhead.tokens, this.saved.skillOverhead.bytes), "ContextSkills"));
          if (this.saved.stale) rows.push(this.line("Saved catalog. Reload can change the next request.", "ContextWarning"));
        } else rows.push(this.line("No saved skill catalog.", "ContextDim"));
      } else {
        rows.push(this.line("Per-tool definition cost · estimates", "ContextTitle"), this.line("Current registrations, not a record of the last request.", "ContextDim"), this.line("Hooks can omit or replace these definitions.", "ContextDim"), this.line("Deferred tools need not enter a request.", "ContextDim"), this.line("% ctx shows potential cost against occupied context.", "ContextDim"), this.line("Tool results remain in chat. Each row includes estimated framing.", "ContextDim"), this.line(""));
        if (this.tools) {
          for (const tool of this.tools) {
            rows.push(this.pair(tool.name + (tool.deferred ? " [deferred]" : ""), this.cost(tool.estimatedTokens, tool.estimatedBytes), "ContextTools"));
            rows.push(this.pair("  Description / schema bytes", number(tool.descriptionBytes) + " / " + number(tool.schemaBytes), "ContextDim"));
          }
          if (!this.tools.length) rows.push(this.line("No registered tools.", "ContextDim"));
        } else rows.push(this.line("Tool inspection needs the updated Yuke executable.", "ContextWarning"));
      }
    }
    this.rows = rows;
    this.scroll = Math.max(0, Math.min(this.scroll, rows.length - this.rect.h));
    this.ctx.tui.root.invalidatePaint();
  }

  draw() {
    for (let i = 0; i < this.rect.h && i + this.scroll < this.rows.length; i++) {
      const spans = this.rows[i + this.scroll].spans;
      for (let n = 0; n < spans.length; n++) {
        const span = spans[n];
        if (span.x < this.rect.w - 1) text(this.rect.x + 1 + span.x, this.rect.y + i, span.value, span.group);
      }
    }
  }

  /** @param {number} delta */
  move(delta) {
    this.scroll = Math.max(0, Math.min(this.scroll + delta, this.rows.length - this.rect.h));
    this.ctx.tui.root.invalidatePaint();
  }
  /** @param {Parameters<Window["onKey"]>[0]} event */
  onKey(event) {
    if (event.type !== "key" || event.event === "release") return true;
    const stroke = keys.strokeOf(event);
    if (["1", "2", "3", "4", "tab", "shift+tab", "left", "right", "h", "l"].includes(stroke)) {
      this.tab = /^[1-4]$/.test(stroke) ? Number(stroke) - 1 : (this.tab + (["shift+tab", "left", "h"].includes(stroke) ? TABS.length - 1 : 1)) % TABS.length;
      this.scroll = 0;
      this.rebuild();
    } else if (stroke === "v") { this.promptGrid = !this.promptGrid; this.rebuild(); }
    else if (stroke === "r") this.refresh();
    else if (["down", "j", "ctrl+n"].includes(stroke)) this.move(1);
    else if (["up", "k", "ctrl+p"].includes(stroke)) this.move(-1);
    else if (["page_down", "ctrl+d"].includes(stroke)) this.move(Math.max(1, this.rect.h - 3));
    else if (["page_up", "ctrl+u"].includes(stroke)) this.move(-Math.max(1, this.rect.h - 3));
    else if (stroke === "home") this.move(-this.rows.length);
    else if (stroke === "end") this.move(this.rows.length);
    else if (["esc", "ctrl+c", "q"].includes(stroke)) this.close();
    return true;
  }
  /** @param {Parameters<Window["onMouse"]>[0]} event */
  onMouse(event) {
    if (event.event !== "press") return true;
    if (event.button === "wheel_up" || event.button === "wheel_down") this.move((event.button === "wheel_up" ? -3 : 3) * (event.count || 1));
    else if (event.button === "left" && event.row - this.rect.y + this.scroll === 2) {
      let x = 1;
      for (let i = 0; i < TABS.length; i++) {
        const width = measure(" " + (i + 1) + " " + TABS[i] + " ");
        if (event.col - this.rect.x >= x && event.col - this.rect.x < x + width) { this.tab = i; break; }
        x += width + 1;
      }
      this.scroll = 0;
      this.rebuild();
    }
    return true;
  }
}

/** Open one owned context dialog. It reads saved metadata on open or refresh. Reader failures stay visible in the dialog. */
/** @param {UiBorrow} c @param {ReturnType<import("yuke").Context["resources"]>} owner @param {() => void} onClose */
export function openContext(c, owner, onClose) {
  const releaseStyles = c.tui.style.set({
        ContextText: { link: "UIPanel", fg: "fg" },
        ContextDim: { link: "UIPanel", fg: "muted", dim: false },
        ContextTitle: { link: "UIPanel", fg: "accent", bold: true },
        ContextActiveTab: { link: "UIPanel", fg: "bg", bg: "accent", bold: true },
        ContextSystem: { link: "UIPanel", fg: "violet" },
        ContextInstructions: { link: "UIPanel", fg: "blue" },
        ContextSkills: { link: "UIPanel", fg: "yellow" },
        ContextTools: { link: "UIPanel", fg: "cyan" },
        ContextChat: { link: "UIPanel", fg: "green" },
        ContextFree: { link: "UIPanel", fg: "muted", dim: false },
        ContextReserve: { link: "UIPanel", fg: "warn" },
        ContextWarning: { link: "UIPanel", fg: "warn" },
  });
  owner.own(releaseStyles);
  const pane = currentPane();
  const dashboard = new ContextDashboard(c, owner, pane?.session.sessionId || null, pane?.session.modelSelector() || "");
  const win = new Window({ name: "context", border: "rounded", title: "Context", titleGroup: "ContextTitle", width: max => Math.min(max, 108), height: max => Math.max(1, max - 2), padding: { x: 0, y: 0 }, content: dashboard, footer: () => dashboard.footer, outsidePress: "ignore" });
  const close = c.tui.overlay(win, onClose);
  owner.own(() => { dashboard.closed = true; close(); return dashboard.pending; });
  dashboard.close = close;
  dashboard.refresh();
}
