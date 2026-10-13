/** @import { UiBorrow } from "../../types.js" */
//! Read status on open or refresh. Draw only cached rows.
import { client, env, exec, fs } from "yuke";
import { currentPane } from "yuke:session";
import { Window, clip, keys, measure, text } from "yuke:ui";
import { versionLabel } from "../build-status/version-label.js";
/** @import { Context } from "yuke" */
/** @typedef {{ label: string, remainingPercent: number, windowSeconds: number, resetsAt: number | null }} QuotaWindow */
/** @typedef {{ provider: string, asOf: string, state: string, error: string, plan: string, windows: QuotaWindow[], creditBalance: number | null, unlimitedCredits: boolean, keyRemaining: number | null, requestsRemaining: number | null, notes: string[] }} Quota */
/** @typedef {{ x: number, value: string, group: string }} Span */
/** @typedef {{ spans: Span[] }} Row */

/** @param {number} value */
function number(value) { return String(Math.round(value)).replace(/\B(?=(\d{3})+(?!\d))/g, ","); }
/** @param {string} value */
function clean(value) { return value.replace(/[\x00-\x1f\x7f-\x9f]/g, " "); }
/** @param {string} value */
function quote(value) { return "'" + value.replaceAll("'", "'\\''") + "'"; }

class StatusView {
  /** @param {UiBorrow} c @param {ReturnType<import("yuke").Context["resources"]>} owner */
  constructor(c, owner) {
    this.ctx = c;
    this.owner = owner;
    const session = currentPane()?.session;
    this.sessionId = session?.sessionId || null;
    this.selector = session?.modelSelector() || "";
    this.rect = { x: 0, y: 0, w: 0, h: 0 };
    this.scroll = 0;
    this.details = false;
    this.closed = false;
    this.loading = false;
    this.error = "";
    this.quotaError = "";
    this.version = "";
    this.directory = "";
    /** @type {Wire.SessionListItem | null} */
    this.item = null;
    /** @type {Wire.ModelInfo | null} */
    this.model = null;
    /** @type {Wire.ProviderInfo | null} */
    this.provider = null;
    /** @type {Quota | null} */
    this.quota = null;
    /** @type {Row[]} */
    this.rows = [];
    this.pending = Promise.resolve();
    this.close = () => {};
  }

  refresh() {
    if (this.closed || this.loading) return;
    this.loading = true;
    this.error = this.quotaError = "";
    this.quota = null;
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
    const init = await client.request("initialize");
    const directory = item?.session.root || (await fs.stat("."))?.path || "Unknown";
    if (this.closed) return;
    this.item = item;
    this.selector = item?.session.model || this.selector;
    this.model = catalog.type === "full" ? catalog.models.find(model => model.selector === this.selector) || null : null;
    this.provider = catalog.type === "full" ? catalog.providers.find(provider => provider.id === this.model?.provider) || null : null;
    this.version = versionLabel(init.engine.version);
    this.directory = directory;
    this.rebuild();
    if (!this.provider) return;
    const home = env.get("HOME") || ".";
    const app = env.get("YUKE_APPNAME") || "yuke";
    const config = (env.get("XDG_CONFIG_HOME") || home + "/.config") + "/" + app;
    try {
      let output = "";
      const result = await exec(["python3", config + "/plugins/status-data.py", this.provider.id, "--config", config].map(quote).join(" "), {
        timeoutMs: 15000, signal: this.owner.signal, onOutput: chunk => { output += chunk; },
      });
      if (this.closed) return;
      if (result.code !== 0) throw new Error("Quota reader failed. Check Python 3 and status-data.py.");
      this.quota = /** @type {Quota} */ (JSON.parse(output));
    } catch (error) {
      if (!this.closed) this.quotaError = error instanceof Error ? error.message : String(error);
    }
  }

  rebuild() {
    if (this.closed) return;
    const width = Math.max(1, this.rect.w - 2);
    /** @type {Row[]} */
    const rows = [];
    /** @param {{ value: string, group: string }[]} parts */
    const segments = parts => {
      let x = 0;
      const spans = [];
      for (const part of parts) {
        if (x >= width) break;
        const value = clip(clean(part.value), width - x);
        spans.push({ x, value, group: part.group });
        x += measure(value);
      }
      rows.push({ spans });
    };
    /** @param {string} value @param {string} [group] */
    const line = (value, group = "StatusText") => {
      if (value) segments([{ value, group }]);
      else rows.push({ spans: [] });
    };
    /** @param {string} label @param {string} value @param {string} [group] */
    const pair = (label, value, group = "StatusText") => {
      const prefix = label.padEnd(16) + "  ";
      if (measure(prefix + value) <= width) segments([{ value: prefix, group: "StatusDim" }, { value, group }]);
      else { line(label, "StatusDim"); line("  " + value, group); }
    };
    /** @param {number} percent @param {string} suffix @param {string} group */
    const bar = (percent, suffix, group) => {
      const label = percent.toFixed(0) + "% " + suffix;
      const cells = Math.max(1, Math.min(48, width - measure(label) - 3));
      const eighths = Math.round(Math.max(0, Math.min(100, percent)) / 100 * cells * 8);
      const whole = Math.floor(eighths / 8);
      const fraction = eighths % 8;
      const filled = "█".repeat(whole) + ["", "▏", "▎", "▍", "▌", "▋", "▊", "▉"][fraction];
      segments([{ value: filled, group }, { value: "░".repeat(cells - whole - (fraction ? 1 : 0)), group: "StatusTrack" },
        { value: "  " + label, group }]);
    };
    const quota = this.quota;
    line(this.model?.name || this.selector || "No model selected", "StatusModel");
    segments([{ value: this.provider?.name || "Provider unknown", group: "StatusTitle" },
      { value: quota?.plan ? "  ·  " + quota.plan : "", group: "StatusPlan" },
      { value: this.item?.session.reasoning ? "  ·  " + this.item.session.reasoning : "", group: "StatusDim" },
      { value: this.sessionId ? "" : "  ·  New draft", group: "StatusDim" }]);
    if (this.error) line("Cannot read status: " + this.error, "StatusDanger");
    if (this.loading) line("Refreshing...", "StatusDim");
    line("");
    line("Account allowance", "StatusTitle");
    if (this.quotaError || quota?.error) line(this.quotaError || quota?.error || "", "StatusDanger");
    else if (!quota) line(this.loading ? "Reading allowance..." : "Account limits unavailable", "StatusDim");
    else {
      for (const limit of quota.windows) {
        line(limit.label.replace(/^Codex /, ""), "StatusText");
        const left = limit.remainingPercent;
        bar(left, "left", left <= 10 ? "StatusDanger" : left <= 25 ? "StatusWarning" : "StatusGood");
        line("Resets " + (limit.resetsAt == null ? "not reported" : new Date(limit.resetsAt * 1000).toLocaleString()), "StatusDim");
        line("");
      }
      if (quota.unlimitedCredits) pair("Credits", "Unlimited", "StatusNumber");
      else if (quota.creditBalance != null) pair("Credits", quota.creditBalance.toFixed(2) + " credits", "StatusNumber");
      if (quota.keyRemaining != null) pair("Key cap left", "$" + quota.keyRemaining.toFixed(2), "StatusNumber");
      if (quota.requestsRemaining != null) pair("Free requests", number(quota.requestsRemaining) + " left today", "StatusNumber");
      if (quota.state === "reported") {
        if (quota.notes.includes("No weekly limit was reported.")) line("Weekly limit not reported", "StatusDim");
        for (const note of quota.notes) {
          if (note.includes("exhausted") || note.includes("invalid quota")) line(note, "StatusWarning");
        }
        line("Updated " + new Date(quota.asOf).toLocaleTimeString(), "StatusDim");
      } else line("Account quota unavailable for this provider", "StatusDim");
    }
    line("");
    line("Context space", "StatusTitle");
    const window = this.model?.context_window;
    const used = this.item?.activity.context_tokens;
    if (window != null && window > 0 && used != null) {
      bar(Math.max(0, window - used) / window * 100, "free", "StatusContext");
      line(number(used) + " / " + number(window) + " tokens used · estimated", "StatusDim");
    } else line(window ? number(window) + " tokens · no request yet" : "Model window unknown", "StatusDim");
    if (this.item) {
      const tokens = this.item.session.usage_total;
      line("");
      pair("Session tokens", number(tokens.input + tokens.output), "StatusNumber");
    }
    if (this.details) {
      line("");
      line("Details", "StatusTitle");
      pair("Model", this.selector, "StatusPlan");
      pair("Provider", this.provider?.id || "Unknown", "StatusTitle");
      pair("Authentication", this.provider ? (this.provider.credential_kind || "No credential") + " / " + this.provider.state : "Unknown", this.provider?.state === "ready" ? "StatusGood" : "StatusWarning");
      line("");
      pair("Directory", this.directory || "Reading...");
      pair("Session", this.sessionId || "New draft", "StatusDim");
      pair("Build", this.version || "Reading...", "StatusDim");
      if (this.item) {
        pair("State", this.item.activity.state.type + " / " + this.item.activity.queued + " queued", this.item.activity.state.type === "idle" ? "StatusGood" : "StatusTitle");
        const config = this.item.activity.config;
        if (config && config.model !== this.selector) pair("Running model", config.model + (config.reasoning ? " / " + config.reasoning : ""), "StatusPlan");
        const tokens = this.item.session.usage_total;
        line("");
        pair("Input / output", number(tokens.input) + " input / " + number(tokens.output) + " output", "StatusNumber");
        pair("Cached input", number(tokens.cache_read) + " tokens (included in input)", "StatusNumber");
        const cost = this.item.session.cost;
        pair("Known API cost", "$" + cost.total.toFixed(2) + (cost.unpriced ? " + " + cost.unpriced + " unpriced replies" : ""), cost.unpriced ? "StatusWarning" : "StatusPlan");
        if (this.item.instruction_sources?.length) line("");
        for (const source of this.item.instruction_sources || []) pair("AGENTS.md", source.path);
      }
      if (window && used != null) pair("Context free", number(Math.max(0, window - used)) + " tokens, not account allowance", "StatusNumber");
      if (this.model?.max_output_tokens) pair("Max output", number(this.model.max_output_tokens) + " tokens per request", "StatusNumber");
      pair("Tokens remaining", "Not reported by provider", "StatusDim");
      line("Yuke does not use Codex sandbox permissions.", "StatusDim");
      if (quota) for (const note of quota.notes) line(note, "StatusDim");
    }
    this.rows = rows;
    this.scroll = Math.max(0, Math.min(this.scroll, rows.length - this.rect.h));
    this.ctx.tui.root.invalidate();
  }

  /** @param {import("yuke:ui").Rect} rect */
  layout(rect) {
    const changed = rect.w !== this.rect.w;
    this.rect = rect;
    if (changed) this.rebuild();
    this.scroll = Math.max(0, Math.min(this.scroll, this.rows.length - rect.h));
  }

  draw() {
    const rect = this.rect;
    for (let i = 0; i < rect.h; i++) {
      const row = this.rows[i + this.scroll];
      if (row == null) break;
      for (let j = 0; j < row.spans.length; j++) {
        const span = row.spans[j];
        text(rect.x + 1 + span.x, rect.y + i, span.value, span.group);
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
    if (stroke === "r") this.refresh();
    else if (stroke === "d") { this.details = !this.details; this.scroll = 0; this.rebuild(); }
    else if (stroke === "j" || stroke === "down") this.move(1);
    else if (stroke === "k" || stroke === "up") this.move(-1);
    else if (stroke === "page_down" || stroke === "ctrl+d") this.move(Math.max(1, this.rect.h - 2));
    else if (stroke === "page_up" || stroke === "ctrl+u") this.move(-Math.max(1, this.rect.h - 2));
    else if (stroke === "home") this.move(-this.rows.length);
    else if (stroke === "end") this.move(this.rows.length);
    else if (stroke === "esc" || stroke === "q" || stroke === "ctrl+c") this.close();
    return true;
  }

  /** @param {Parameters<Window["onMouse"]>[0]} event */
  onMouse(event) {
    if (event.event === "press" && (event.button === "wheel_up" || event.button === "wheel_down")) this.move(event.button === "wheel_up" ? -3 : 3);
    return true;
  }
}

/** Open an owned status snapshot. The owner cancels its reader. Unknown quotas stay unknown; read failures appear in the view.
 * @param {UiBorrow} c @param {ReturnType<import("yuke").Context["resources"]>} owner @param {() => void} onClose
 */
export function openStatus(c, owner, onClose) {
  owner.own(c.tui.style.set({
    StatusText: { link: "UIPanel", fg: "fg" },
    StatusTitle: { link: "UIPanel", fg: "accent", bold: true },
    StatusModel: { link: "UIPanel", fg: "strongFg", bold: true },
    StatusPlan: { link: "UIPanel", fg: "violet" },
    StatusDim: { link: "UIDim", dim: false },
    StatusTrack: { link: "UIDim", dim: false },
    StatusGood: { link: "UIPanel", fg: "green", bold: true },
    StatusContext: { link: "UIPanel", fg: "cyan" },
    StatusNumber: { link: "UIPanel", fg: "cyan", bold: true },
    StatusWarning: { link: "UIPanel", fg: "warn" },
    StatusDanger: { link: "UIPanel", fg: "danger" },
  }));
  const view = new StatusView(c, owner);
  const win = new Window({ name: "status", border: "rounded", title: "Status", titleGroup: "StatusTitle",
    width: max => Math.min(max, 84), contentHeight: max => Math.min(max, view.rows.length),
    padding: { x: 0, y: 0 }, content: view, footer: "r refresh · d details · esc close", footerGroup: "StatusTitle", outsidePress: "ignore" });
  const close = c.tui.overlay(win, onClose);
  owner.own(() => { view.closed = true; close(); return view.pending; });
  view.close = close;
  view.refresh();
}
