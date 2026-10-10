//! Complete explicit $skill mentions and admit their bodies through the engine.
import { client, env, exec } from "yuke";
import { ChatView } from "yuke:chat";
import { ui } from "yuke:ui";

/** @import { Picker, Window } from "yuke:ui" */
/** @typedef {{ name: string, description: string, path: string, canonical_path: string }} Skill */
/** @typedef {{ start: number, end: number, query: string }} Token */

/** @param {string} value */
function quote(value) {
  return "'" + value.replaceAll("'", "'\\''") + "'";
}

/** Read explicit mentions outside code spans. An escaped dollar stays literal. @param {string} text */
function mentions(text) {
  const names = [];
  const pattern = /(`+)[\s\S]*?\1|\\\$|(^|\s)\$([a-z0-9]+(?:-[a-z0-9]+)*)(?=$|[^\w$-])/g;
  let match;
  while ((match = pattern.exec(text)) !== null) {
    if (match[3]) names.push(match[3]);
  }
  return names;
}

/** The editable mention at the caret, or null outside a mention. @param {ChatView} pane @returns {Token | null} */
function tokenAt(pane) {
  const input = pane.composer.input;
  const prefix = input.beforeCaret();
  const match = /(?:^|\s)\$([a-z0-9-]*)$/.exec(prefix);
  if (!match || prefix.replace(/(`+)[\s\S]*?\1/g, "").includes("`")) return null;
  let end = input.caret;
  while (end < input.text.length && /[a-z0-9-]/.test(input.text[end])) end++;
  return { start: input.caret - match[1].length - 1, end, query: match[1] };
}
/** Register the migrated dollar-skills operations. The plugin owns registrations; host failures throw. @param {import("yuke").Context} parent */
export default function(parent) {

    const config = env.get("XDG_CONFIG_HOME") || (env.get("HOME") || ".") + "/.config";
    const helper = config + "/" + (env.get("YUKE_APPNAME") || "yuke") + "/plugins/dollar-skills.py";

    /** @param {string} [root] */
    async function scan(root) {
      const result = await exec("python3 " + quote(helper) + " scan" + (root == null ? "" : " " + quote(root)), {
        signal: parent.signal, maxBytes: 65536,
      });
      if (result.code !== 0 || result.stdoutDropped > 0) throw new Error(result.stderr.trim() || "Skill catalog exceeds 64 KiB.");
      return JSON.parse(result.stdout);
    }

    /** @param {string | null} sessionId @param {string} [root] @returns {Promise<Skill[]>} */
    async function catalog(sessionId, root) {
      if (sessionId) return Array.from((await client.sessionGet(sessionId)).skills || []);
      return scan(root);
    }

    parent.hook("input.before", (input) => {
      for (let i = 0; i < input.content.length; i++) {
        const part = input.content[i];
        if (part.type === "text" && part.text.includes("$")) return expand(input);
      }
    });

    /** @param {{ session_id: string | null, content: Wire.ContentPart[], skills?: string[], create?: Wire.CreateSession }} input @returns {Promise<{ replace: { content: Wire.ContentPart[], skills: string[] } } | undefined>} */
    async function expand(input) {
      const names = new Set();
      for (let i = 0; i < input.content.length; i++) {
        const part = input.content[i];
        if (part.type !== "text") continue;
        const found = mentions(part.text);
        for (let j = 0; j < found.length; j++) names.add(found[j]);
      }
      if (names.size === 0) return;
      const all = await catalog(input.session_id, input.create?.workspace_path);
      const selected = all.filter((skill) => names.has(skill.name));
      if (selected.length === 0) return;
      const skills = input.skills ? input.skills.slice() : [];
      for (let i = 0; i < selected.length; i++) {
        if (!skills.includes(selected[i].name)) skills.push(selected[i].name);
      }
      return { replace: { content: input.content, skills } };
    }

    {
const tuiBorrow = parent.get("tui");
if (tuiBorrow) {
const c = { ctx: parent, tui: tuiBorrow };

      /** @type {Skill[]} */
      let all = [];
      /** @type {Map<string, { text: string, detail: string }>} */
      const rows = new Map();
      let loadedFor = "";
      let generation = 0;
      /** @type {{ pane: ChatView, picker: Picker<Skill>, win: Window, query: string, start: number } | null} */
      let float = null;
      /** @type {{ pane: ChatView, text: string } | null} */
      let dismissed = null;

      function close() {
        if (float) c.tui.root.popOverlay(float.win);
        float = null;
      }

      /** @param {ChatView} pane @param {Skill | null} skill */
      function complete(pane, skill) {
        const token = tokenAt(pane);
        if (!token || !skill) return close();
        close();
        const suffix = pane.composer.text.slice(token.end);
        pane.composer.input.replace(token.start, token.end, "$" + skill.name + (/^\s/.test(suffix) ? "" : " "));
      }

      /** @param {ChatView} pane */
      function loadCatalog(pane) {
        const key = pane.session.sessionId || "draft";
        if (loadedFor === key) return;
        loadedFor = key;
        all = [];
        close();
        const token = ++generation;
        catalog(pane.session.sessionId).then((skills) => {
          if (!c.ctx.alive || token !== generation) return;
          all = skills;
          rows.clear();
          let column = 0;
          for (let i = 0; i < skills.length; i++) column = Math.max(column, skills[i].name.length + 3);
          for (let i = 0; i < skills.length; i++) {
            const skill = skills[i];
            rows.set(skill.name, { text: ("$" + skill.name).padEnd(column), detail: skill.description.replace(/\s+/g, " ") });
          }
          sync();
        }).catch((error) => {
          if (c.ctx.alive && token === generation) c.ctx.interaction.notify("Skill completion unavailable: " + String(error), "warn");
        });
      }

      function sync() {
        const pane = c.tui.root.active;
        if (!(pane instanceof ChatView) || pane.focus !== "composer" || c.tui.root.focused !== pane) return close();
        loadCatalog(pane);
        if (!pane.composer.text.includes("$")) return close();
        syncMention(pane);
      }

      /** @param {ChatView} pane */
      function syncMention(pane) {
        const token = tokenAt(pane);
        if (!token || (dismissed?.pane === pane && dismissed.text === pane.composer.text)) return close();
        dismissed = null;
        const ranked = all.filter((skill) => skill.name.startsWith(token.query));
        if (ranked.length === 0) return close();
        if (float && (float.pane !== pane || float.start !== token.start)) close();
        if (float) {
          if (float.query === token.query) return;
          float.picker.setSource(ranked);
          float.picker.list.selectKey(ranked[0].name);
          float.query = token.query;
          return;
        }
        const picker = ui.pick({
          name: "dollar-skills", items: ranked, filter: false, modal: false,
          border: "none", panelGroup: "UIFloat", maxRows: 6,
          anchor: () => pane.composer.rect,
          key: (skill) => skill.name,
          format: (skill) => rows.get(skill.name) || "",
          keymap: {
            up: "prev", "ctrl+p": "prev", down: "next", "ctrl+n": "next",
            tab: (_event, content) => complete(pane, content.list.selected()),
            left: (event) => { close(); pane.composer.onKey(event); },
            right: (event) => { close(); pane.composer.onKey(event); },
            home: (event) => { close(); pane.composer.onKey(event); },
            end: (event) => { close(); pane.composer.onKey(event); },
            "ctrl+a": (event) => { close(); pane.composer.onKey(event); },
            "ctrl+e": (event) => { close(); pane.composer.onKey(event); },
          },
          onAccept: (skill) => { float = null; complete(pane, skill); },
          onCancel: () => { float = null; dismissed = { pane, text: pane.composer.text }; },
        });
        c.tui.overlay(picker.win);
        float = { pane, picker: picker.content, win: picker.win, query: token.query, start: token.start };
      }

      c.ctx.advise(client, "sessionReloadContext", "around", (next, sessionId) => next(sessionId).then((result) => {
        if (c.ctx.alive && loadedFor === sessionId) {
          generation++;
          loadedFor = "";
          all = [];
          close();
          sync();
        }
        return result;
      }));

      c.ctx.on("composer.changed", (composer) => {
        if (dismissed && dismissed.pane.composer === composer && dismissed.text !== composer.text) dismissed = null;
        if (float || c.tui.root.active instanceof ChatView && c.tui.root.active.composer.text.includes("$")) sync();
      });
      c.ctx.on("pane.focused", sync);
      c.ctx.on("region.focused", sync);
      c.ctx.on("pane.closed", sync);
      c.ctx.on("session.current.changed", sync);
      c.ctx.own(close);
      sync();
}
}
  
}
