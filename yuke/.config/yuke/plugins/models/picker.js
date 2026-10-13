//! Select models and edit their persistent aliases in one numbered picker.
import { client, env, exec, fs } from "yuke";
import { currentPane } from "yuke:session";
/** @import { Session } from "yuke:session" */
import { ui } from "yuke:ui";

/** @import { Picker } from "yuke:ui" */
/** @typedef {{ alias: string, model?: string, latest?: { provider: string, family: "sol" | "luna" }, effort?: string, key?: string }} ModelPreset */
/** @typedef {{ version: 1, revision: number, presets: ModelPreset[] }} AliasState */
/** @typedef {{ model: Wire.ModelInfo, aliases: ModelPreset[], display: { text: string, right: string, group: string } }} ModelRow */

const RESERVED = new Set(["model", "models", "effort", "new", "clear", "reload", "exit", "close", "sessions", "resume", "search", "work", "todo", "checkpoint", "questions", "usage", "context", "login", "logout", "reload-providers", "quit"]);

/** @param {unknown} value @returns {ModelPreset[]} */
function validatePresets(value) {
  if (!Array.isArray(value) || value.length > 64) throw new Error("At most 64 model aliases are allowed.");
  const aliases = new Set();
  for (const preset of value) {
    if (!preset || typeof preset !== "object" || Object.keys(preset).some(key => !["alias", "model", "latest", "effort", "key"].includes(key))) throw new Error("Invalid model alias entry.");
    if (typeof preset.alias !== "string" || !/^[a-z][a-z0-9-]{0,31}$/.test(preset.alias) || RESERVED.has(preset.alias) || aliases.has(preset.alias)) throw new Error("Invalid or duplicate model alias: " + preset.alias);
    if (!!preset.model === !!preset.latest) throw new Error("Set model or latest for /" + preset.alias);
    for (const key of ["model", "effort", "key"]) {
      if (preset[key] !== undefined && (typeof preset[key] !== "string" || preset[key].length > 256 || /[\x00-\x1f\x7f-\x9f]/.test(preset[key]))) throw new Error("Invalid alias " + key);
    }
    if (preset.latest && (Object.keys(preset.latest).some(key => !["provider", "family"].includes(key)) || typeof preset.latest.provider !== "string" || !preset.latest.provider || preset.latest.provider.length > 256 || /[\x00-\x1f\x7f-\x9f]/.test(preset.latest.provider) || !["sol", "luna"].includes(preset.latest.family))) throw new Error("Invalid model family for /" + preset.alias);
    aliases.add(preset.alias);
  }
  return /** @type {ModelPreset[]} */ (value);
}

/** @param {string} text */
function quote(text) { return "'" + text.replaceAll("'", "'\\''") + "'"; }

/** @param {ModelPreset} preset @param {readonly Wire.ModelInfo[]} models @returns {Wire.ModelInfo | undefined} */
function resolvePreset(preset, models) {
  if (!preset.latest) return models.find(model => model.selector === preset.model);
  const pattern = new RegExp("^gpt-(\\d+(?:\\.\\d+)*)-" + preset.latest.family + "$");
  /** @type {Wire.ModelInfo | undefined} */
  let best;
  /** @type {number[]} */
  let version = [];
  for (const model of models) {
    if (model.provider !== preset.latest.provider) continue;
    const match = pattern.exec(model.id);
    if (!match) continue;
    const candidate = match[1].split(".").map(Number);
    let order = 0;
    for (let i = 0; i < Math.max(candidate.length, version.length); i++) {
      order = (candidate[i] || 0) - (version[i] || 0);
      if (order !== 0) break;
    }
    if (!best || order > 0) { best = model; version = candidate; }
  }
  return best;
}
/** Register enabled pickers and aliases with shared reasoning state. The context owns commands, advice and shortcuts. @param {import("yuke").Context} parent @param {import("yuke:ui").Tui} tui @param {{ picker: boolean, effortPicker: boolean, aliases: boolean, modelKey: string, effortKey: string }} options @param {ReturnType<typeof import("./state.js").modelState>} selection */
export default function(parent, tui, options, selection) {
  const defaults = validatePresets([{ alias: "sh", latest: { provider: "openai-codex", family: "sol" }, effort: "high", key: "ctrl+x s" }, { alias: "lm", latest: { provider: "openai-codex", family: "luna" }, effort: "medium", key: "ctrl+x l" }]);
  const config = (env.get("XDG_CONFIG_HOME") || (env.get("HOME") || ".") + "/.config") + "/" + (env.get("YUKE_APPNAME") || "yuke");
  const file = config + "/model-aliases.json";
  const helper = config + "/plugins/model-alias-store.py";
  const c = { ctx: parent, tui };
  /** @type {AliasState} */
  let state = { version: 1, revision: 0, presets: options.aliases ? defaults : [] };
  /** @type {(() => void)[]} */
  let registrations = [];
  let editing = false;
  /** @param {ModelPreset[]} presets */
  function registerAliases(presets) {
    if (!options.aliases) return;
    /** @type {(() => void)[]} */
    const next = [];
    /** @type {Record<string, string>} */
    const bindings = {};
    try {
      for (const preset of presets) {
        const command = "models:preset-" + preset.alias;
        next.push(c.tui.command.add(command, {
          desc: "use /" + preset.alias + " · " + (preset.model || "latest " + preset.latest?.family) + (preset.effort ? " · " + preset.effort : ""),
          slash: preset.alias,
          run: () => run("model", preset.alias),
        }));
        if (preset.key) bindings[preset.key] = command;
      }
      next.push(c.tui.keymap.add(bindings, "chat && !overlay"));
    } catch (error) {
      for (const remove of next) remove();
      throw error;
    }
    for (const remove of registrations) remove();
    registrations = next;
  }

  async function loadAliases() {
    if (!options.aliases) return;
    const exists = await fs.stat(file);
    if (!c.ctx.alive) return;
    const next = exists ? JSON.parse(await fs.readFile(file)) : { version: 1, revision: 0, presets: options.aliases ? defaults : [] };
    if (!next || next.version !== 1 || !Number.isSafeInteger(next.revision) || next.revision < 0 || Object.keys(next).some(key => !["version", "revision", "presets"].includes(key))) throw new Error("Invalid model alias file.");
    validatePresets(next.presets);
    if (!c.ctx.alive) return;
    if (registrations.length === 0 || next.revision !== state.revision) {
      registerAliases(next.presets);
      state = next;
    }
  }
  void loadAliases().catch(error => { if (c.ctx.alive) c.ctx.interaction.notify("Cannot load model aliases: " + String(error), "error"); });

  /** @template T @param {string} title @param {T[]} items @param {(item: T) => { text: string, right?: string, group?: string }} format @param {(item: T) => void} accept @param {{ footer?: string, key?: (item: T) => string, keymap?: Record<string, (event: unknown, picker: Picker<T>) => void> }} [extra] */
  function pick(title, items, format, accept, extra = {}) {
    const keymap = { ...extra.keymap };
    for (let i = 1; i <= 9; i++) {
      keymap[String(i)] = (_event, picker) => {
        if (picker.list.items.length < i) return;
        picker.list.navEdge(-1);
        picker.list.navBy(i - 1);
        picker.accept();
      };
    }
    const result = ui.pick({
      title,
      footer: extra.footer || "1–9 select first rows · type to filter · enter select · esc close",
      items, key: extra.key, maxRows: 9,
      filterText: item => { const row = format(item); return row.text + " " + (row.right || ""); },
      format: (item, index) => { const row = format(item); return { ...row, text: (index + 1) + ") " + row.text }; },
      keymap, onAccept: accept,
    });
    c.tui.overlay(result.win);
    return result.content;
  }

  /** @param {Session} session @param {string | null} id @param {number} generation */
  function live(session, id, generation) {
    return c.ctx.alive && currentPane()?.session === session && session.sessionId === id && session.gen === generation;
  }

  /** @param {"model" | "effort"} mode @param {string} [query] @param {{ filter: string, selector: string }} [restore] */
  async function run(mode, query = "", restore) {
    const session = currentPane()?.session;
    if (!session) return;
    const id = session.sessionId;
    const generation = session.gen;
    const selector = session.modelSelector();
    try {
      await loadAliases();
      await client.catalogReload();
      const catalog = await client.catalogList(null);
      if (!("models" in catalog) || !live(session, id, generation)) return;
      const effort = await selection.effortOf(session);
      if (!live(session, id, generation) || session.modelSelector() !== selector) return;
      const models = catalog.models.slice().sort((a, b) =>
        (a.provider < b.provider ? -1 : a.provider > b.provider ? 1 : 0) ||
        (a.name > b.name ? -1 : a.name < b.name ? 1 : 0));
      /** @param {Wire.ModelInfo} model @param {string} [requested] */
      const select = (model, requested) => {
        if (!live(session, id, generation)) return;
        const provider = catalog.providers.find(row => row.id === model.provider);
        if (provider && provider.state !== "ready") return c.ctx.interaction.notify(model.provider + ": " + provider.state + ". Use /login or update providers.json.", "warn");
        if (requested !== undefined && !model.reasoning_levels.includes(requested) && !(requested === "" && model.reasoning_levels.length === 0)) return c.ctx.interaction.notify("Unsupported effort " + requested + " for " + model.name, "warn");
        const next = requested !== undefined ? requested : model.reasoning_levels.includes(effort) ? effort : model.default_reasoning || model.reasoning_levels[0] || "";
        session.setModel(model, next);
      };
      query = typeof query === "string" ? query.trim() : "";
      if (mode === "effort") {
        const model = models.find(row => row.selector === selector);
        if (!model) return c.ctx.interaction.notify("Select a model first with /model.", "warn");
        const levels = model.reasoning_levels.slice();
        if (!levels.length) return c.ctx.interaction.notify(model.name + " has no effort levels.");
        if (query) {
          const level = /^\d+$/.test(query) ? levels[Number(query) - 1] : levels.find(value => value === query);
          if (level === undefined) return c.ctx.interaction.notify("Unknown effort. Choose: " + levels.join(", "), "warn");
          return select(model, level);
        }
        return pick(model.name + " · effort", levels, level => ({ text: level, right: level === effort ? "current" : "" }), level => select(model, level));
      }
      if (query && !/^\d+$/.test(query)) {
        const alias = state.presets.find(value => value.alias === query);
        if (alias) {
          const model = resolvePreset(alias, models);
          if (!model) return c.ctx.interaction.notify("No model for /" + alias.alias + ": " + (alias.model || alias.latest?.provider + " latest " + alias.latest?.family), "warn");
          return select(model, alias.effort);
        }
        const matches = models.filter(model => model.selector === query || model.id === query || model.name === query);
        if (matches.length === 1) return select(matches[0]);
        return c.ctx.interaction.notify(matches.length ? "Ambiguous model. Use its provider/model selector." : "Unknown model: " + query, "warn");
      }
      if (!models.length) return c.ctx.interaction.notify("No models in the catalog.", "warn");
      /** @type {Map<string, ModelRow>} */
      const bySelector = new Map();
      for (const model of models) bySelector.set(model.selector, { model, aliases: [], display: { text: model.name, right: model.provider, group: "UIItem" } });
      /** @type {ModelRow[]} */
      const rows = [];
      for (const alias of state.presets) {
        const model = resolvePreset(alias, models);
        if (!model) continue;
        const row = /** @type {ModelRow} */ (bySelector.get(model.selector));
        if (!row.aliases.length) rows.push(row);
        row.aliases.push(alias);
      }
      for (const row of bySelector.values()) {
        const provider = catalog.providers.find(value => value.id === row.model.provider);
        if (row.aliases.length) {
          row.display.text = "★ " + row.model.name;
          row.display.right = row.aliases.map(alias => "alias " + alias.alias + (alias.effort ? " · " + alias.effort : "")).join(", ") + " · " + row.model.provider;
          row.display.group = "UITitle";
        } else rows.push(row);
        if (row.model.selector === selector) row.display.right += " · current";
        if (provider && provider.state !== "ready") { row.display.right += " · " + provider.state; row.display.group = "UIDim"; }
      }
      if (query) {
        const row = rows[Number(query) - 1];
        if (!row) return c.ctx.interaction.notify("Unknown model: " + query, "warn");
        return select(row.model, row.aliases[0]?.effort);
      }
      const editorRevision = state.revision;
      /** @param {Picker<ModelRow>} picker @param {"alias" | "remove" | "effort"} action */
      const edit = async (picker, action) => {
        const row = picker.list.selected();
        if (!row || editing || !live(session, id, generation)) return;
        editing = true;
        const filter = picker.query;
        picker.close();
        try {
          /** @type {ModelPreset | undefined} */
          let existing = row.aliases[0];
          if (row.aliases.length > 1) {
            const name = await c.ctx.interaction.select("Choose an alias for " + row.model.name, row.aliases.map(alias => alias.alias));
            if (name === undefined) return;
            existing = row.aliases.find(alias => alias.alias === name);
          }
          if (action !== "alias" && !existing) { c.ctx.interaction.notify("Set an alias first with Ctrl+A."); return; }
          let next = state.presets.slice();
          if (action === "remove") {
            if (!await c.ctx.interaction.confirm("Remove alias /" + existing?.alias + "?", "The model stays in the list. This removes its alias and shortcut.")) return;
            next = next.filter(alias => alias.alias !== existing?.alias);
          } else if (action === "alias") {
            const answer = await c.ctx.interaction.input("Alias for " + row.model.name, existing ? "Current: /" + existing.alias + "; blank removes it" : "Short name, for example sh");
            if (answer === undefined) return;
            const alias = answer.trim().replace(/^\//, "");
            if (!alias) {
              if (!existing) return;
              next = next.filter(value => value.alias !== existing?.alias);
            } else {
              const command = "models:preset-" + alias;
              if (c.tui.command.list().some(entry => entry.slash === alias && entry.name !== command)) throw new Error("/" + alias + " already belongs to another command.");
              const value = existing ? { ...existing, alias } : { alias, model: row.model.selector, effort: row.model.reasoning_levels.includes(effort) ? effort : row.model.default_reasoning || row.model.reasoning_levels[0] || "" };
              if (existing) next[next.findIndex(value => value.alias === existing?.alias)] = value;
              else next.push(value);
            }
          } else {
            const levels = row.model.reasoning_levels.slice();
            if (!levels.length) { c.ctx.interaction.notify("This model has no effort levels."); return; }
            /** @type {() => unknown} */
            let release = () => {};
            const value = await new Promise((resolve) => {
              release = c.ctx.own(() => resolve(undefined));
              const choices = pick(row.model.name + " · alias effort", levels, level => ({ text: level }), level => resolve(level));
              choices.onCancel = () => resolve(undefined);
              choices.list.selectKey(existing?.effort);
            }).finally(() => { release(); });
            if (value === undefined) return;
            next = next.map(alias => alias.alias === existing?.alias ? { ...alias, effort: /** @type {string} */ (value) } : alias);
          }
          if (!live(session, id, generation)) return;
          validatePresets(next);
          const result = await exec("python3 " + quote(helper) + " " + quote(file) + " " + quote(JSON.stringify({ version: 1, revision: editorRevision, presets: next })), { signal: c.ctx.signal, maxBytes: 65536 });
          if (result.code !== 0 || result.stdoutDropped) throw new Error(result.stderr.trim() || "Could not save model aliases.");
          if (!c.ctx.alive) return;
          const saved = JSON.parse(result.stdout);
          registerAliases(saved.presets);
          state = saved;
          c.ctx.interaction.notify("Model aliases saved.");
        } catch (error) {
          if (c.ctx.alive) c.ctx.interaction.notify("Cannot save model aliases: " + String(error), "error");
        } finally {
          editing = false;
          if (live(session, id, generation)) void run("model", "", { filter, selector: row.model.selector });
        }
      };
      const picker = pick("select a model", rows, row => row.display, row => {
        if (!live(session, id, generation)) return;
        const model = row.model;
        const levels = model.reasoning_levels.slice();
        if (!levels.length) return select(model, "");
        const requested = row.aliases[0]?.effort || effort;
        const preferred = levels.includes(requested) ? requested : model.default_reasoning || levels[0];
        const choices = pick(model.name + " · effort", levels, level => ({ text: level, right: level === preferred ? "suggested" : "" }), level => select(model, level));
        choices.list.selectKey(preferred);
      }, {
        key: row => row.model.selector,
        footer: options.aliases ? "1–9 · Ctrl+A alias · Ctrl+R remove · Ctrl+E effort · esc close" : "1–9 select · esc close",
        keymap: options.aliases ? {
          "ctrl+a": (_event, picker) => { void edit(picker, "alias"); },
          "ctrl+r": (_event, picker) => { void edit(picker, "remove"); },
          "ctrl+e": (_event, picker) => { void edit(picker, "effort"); },
        } : {},
      });
      if (restore) { picker.query = restore.filter; picker.list.selectKey(restore.selector); }
    } catch (error) {
      if (live(session, id, generation)) c.ctx.interaction.notify("Model controls failed: " + String(error), "error");
    }
  }
  if (options.picker) c.ctx.advise(c.tui.command.map["model:pick"], "run", "around", (_next, query) => run("model", typeof query === "string" ? query : ""));
  if (options.effortPicker) c.tui.command.add("effort", { desc: "choose reasoning effort for the current model", slash: true, args: true, run: (/** @type {string | undefined} */ query) => run("effort", query) });
  /** @type {Record<string, string>} */
  const bindings = {};
  if (options.picker && options.modelKey) bindings[options.modelKey] = "model:pick";
  if (options.effortPicker && options.effortKey) bindings[options.effortKey] = "models:effort";
  c.tui.keymap.add(bindings, "chat && !overlay");
}
