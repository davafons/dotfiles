//! Complete the path at the focused composer's caret without submitting its draft.
import { fs } from "yuke";
import { ui } from "yuke:ui";
import { ChatView } from "yuke:chat";
/** @import { Context } from "yuke" */
/** @import { Picker, Window, Tui } from "yuke:ui" */
/** @type {Tui["root"]} */
let root;
/** @returns {ChatView | null} */
function focusedChat() { const view = root.active; return view instanceof ChatView ? view : null; }
/** @typedef {{ name: string, isDirectory: boolean }} Entry */
const CONTROL_NAME = /[\r\n]/;
const QUOTED_PATH = /[\s"'`]/;

/** @typedef {{ from: number, to: number, directory: string, prefix: string, quote: string }} PathWord */

/** @param {string} text @param {number} caret @returns {PathWord | null} */
function directoryWord(text, caret) {
  let from = 3;
  while (text[from] === " " || text[from] === "\t") from++;
  const first = text[from];
  const quote = first === '"' || first === "'" || first === "`" ? first : "";
  if (quote) from++;
  let to = text.length;
  if (quote && text[to - 1] === quote) to--;
  if (caret < from || caret > to) return null;
  const word = text.slice(from, caret);
  const slash = word.lastIndexOf("/");
  return { from, to, directory: slash < 0 ? "./" : word.slice(0, slash + 1), prefix: word.slice(slash + 1), quote };
}

/** @param {string} text @param {number} caret @returns {PathWord | null} */
function pathWord(text, caret) {
  if (text[0] === "/" && text[1] === "c" && text[2] === "d" && (text[3] === " " || text[3] === "\t")) return directoryWord(text, caret);
  let from = 0, quote = "";
  for (let i = 0; i < caret; i++) {
    const char = text[i];
    if (quote) {
      if (char === quote || char === "\n") { quote = ""; from = i + 1; }
    } else if (i === from && (char === '"' || char === "'" || char === "`")) {
      quote = char;
      from = i + 1;
    } else if (char === " " || char === "\t" || char === "\n" || char === "(" || char === "=") from = i + 1;
  }
  const word = text.slice(from, caret);
  const slash = word.lastIndexOf("/");
  if (slash < 0 || word.startsWith("//") || word.includes(":")) return null;
  if (word[0] === "/" && slash === 0) return null;
  if (word[0] === "~" && !word.startsWith("~/")) return null;
  let to = caret;
  while (to < text.length) {
    const char = /** @type {string} */ (text[to]);
    if (quote ? char === quote || char === "\n" : " \t\r\n)".includes(char)) break;
    to++;
  }
  return { from, to, directory: word.slice(0, slash + 1), prefix: word.slice(slash + 1), quote };
}

// One active path keeps one directory read; a generation change discards its stale result.
class PathCompletion {
  /** @param {Context} ctx @param {Tui} tui @param {import("yuke").Capabilities["composer-vim"] | null} vim */
  constructor(ctx, tui, vim) {
    this.ctx = ctx;
    this.tui = tui;
    this.vim = vim;
    this.active = false;
    this.completing = false;
    this.generation = 0;
    this.directory = "";
    /** @type {Entry[] | null} */
    this.entries = null;
    /** @type {{ chat: ChatView, picker: Picker<Entry>, win: Window, text: string, caret: number, word: PathWord } | null} */
    this.float = null;
    /** @type {{ chat: ChatView, text: string, caret: number } | null} */
    this.dismissed = null;
  }

  /** Drop the menu and invalidate its pending directory read. */
  close() {
    if (this.float) root.popOverlay(this.float.win);
    this.float = null;
    this.active = false;
    this.directory = "";
    this.entries = null;
    this.generation++;
  }

  /** @param {ChatView | null} chat */
  sync(chat) {
    if (this.completing) return;
    if (!chat || root.focused !== chat || chat.focus !== "composer" || this.vim && this.vim.mode(chat.composer) !== "insert") return this.close();
    const input = chat.composer.input;
    const held = this.dismissed;
    if (held && held.chat === chat && held.text === input.text && held.caret === input.caret) return this.close();
    this.dismissed = null;
    const word = pathWord(input.text, input.caret);
    if (!word) return this.close();
    if (this.float && this.float.chat !== chat) this.close();
    this.active = true;
    if (this.directory !== word.directory) {
      this.close();
      this.active = true;
      this.directory = word.directory;
      const generation = this.generation;
      fs.readDir(word.directory).then((entries) => {
        if (!this.ctx.alive || generation !== this.generation) return;
        entries.sort((a, b) => a.isDirectory !== b.isDirectory ? (a.isDirectory ? -1 : 1) : a.name < b.name ? -1 : a.name > b.name ? 1 : 0);
        this.entries = entries;
        this.sync(focusedChat());
      }, () => {
        if (!this.ctx.alive || generation !== this.generation) return;
        this.entries = [];
      });
      return;
    }
    if (!this.entries) return;
    const directoriesOnly = input.text[0] === "/" && input.text[1] === "c" && input.text[2] === "d" && (input.text[3] === " " || input.text[3] === "\t");
    const ranked = [];
    for (let i = 0; i < this.entries.length; i++) {
      const entry = /** @type {Entry} */ (this.entries[i]);
      if (directoriesOnly && !entry.isDirectory) continue;
      if (!entry.name.startsWith(word.prefix) || (word.prefix[0] !== "." && entry.name[0] === ".")) continue;
      if (CONTROL_NAME.test(entry.name) || (word.quote ? entry.name.includes(word.quote) : entry.name.includes('"') && entry.name.includes("'") && entry.name.includes("`"))) continue;
      ranked.push(entry);
    }
    if (ranked.length === 0) {
      if (this.float) root.popOverlay(this.float.win);
      this.float = null;
      return;
    }
    if (this.float) {
      const changed = this.float.text !== input.text || this.float.caret !== input.caret;
      this.float.picker.setSource(ranked);
      if (changed) this.float.picker.list.selectKey(/** @type {Entry} */ (ranked[0]).name);
      this.float.text = input.text;
      this.float.caret = input.caret;
      this.float.word = word;
    } else this.open(chat, word, ranked);
  }

  /** @param {ChatView} chat @param {PathWord} word @param {Entry[]} entries */
  open(chat, word, entries) {
    /** @param {Parameters<ChatView["composer"]["onKey"]>[0]} ev */
    const move = (ev) => {
      chat.composer.onKey(ev);
      this.sync(chat);
    };
    const p = ui.pick({
      name: "paths", items: entries, filter: false, modal: false,
      border: "none", panelGroup: "UIFloat", maxRows: 6,
      anchor: () => chat.composer.rect,
      key: (entry) => entry.name,
      format: (entry) => entry.name + (entry.isDirectory ? "/" : ""),
      closeOnAccept: false,
      keymap: {
        up: "prev", "ctrl+p": "prev", down: "next", "ctrl+n": "next",
        tab: (_ev, content) => this.complete(content.list.selected()),
        left: move, right: move, home: move, end: move, "ctrl+a": move, "ctrl+e": move,
      },
      onAccept: (entry) => this.complete(entry),
      onCancel: () => {
        this.dismissed = { chat, text: chat.composer.text, caret: chat.composer.input.caret };
        this.close();
      },
    });
    this.tui.overlay(p.win);
    this.float = { chat, picker: p.content, win: p.win, text: chat.composer.text, caret: chat.composer.input.caret, word };
  }

  /** @param {Entry | null} entry */
  complete(entry) {
    const held = this.float;
    if (!held || !entry) return;
    const input = held.chat.composer.input;
    if (focusedChat() !== held.chat || input.text !== held.text || input.caret !== held.caret) return this.close();
    let replacement = held.word.directory + entry.name + (entry.isDirectory ? "/" : "");
    const closeQuote = held.word.quote && held.word.to === input.text.length && (input.text.startsWith("/cd ") || input.text.startsWith("/cd\t"));
    if (closeQuote) replacement += held.word.quote;
    const quoted = !held.word.quote && QUOTED_PATH.test(replacement);
    if (quoted) {
      const quote = !replacement.includes('"') ? '"' : !replacement.includes("'") ? "'" : "`";
      replacement = quote + replacement + quote;
    }
    this.close();
    this.completing = true;
    input.replace(held.word.from, held.word.to, replacement);
    this.completing = false;
    if (entry.isDirectory) {
      if (quoted || closeQuote) input.caret--;
      this.sync(held.chat);
    } else {
      this.close();
      this.dismissed = { chat: held.chat, text: input.text, caret: input.caret };
    }
  }
}

/** Complete paths at the draft caret when TUI exists. Missing directories show no menu; registration failures throw. @param {Context} ctx */
export default function (ctx) {
  const tui = ctx.get("tui");
  if (!tui) return;
  root = tui.root;
  const paths = new PathCompletion(ctx, tui, ctx.get("composer-vim"));
  ctx.own(() => paths.close());
  const sync = () => {
    const chat = focusedChat();
    const typing = chat && root.focused === chat && chat.focus === "composer";
    if (paths.active || typing && chat.composer.text.indexOf("/") >= 0) paths.sync(typing ? chat : null);
  };
  ctx.on("composer.changed", sync);
  ctx.on("pane.focused", sync);
  ctx.on("region.focused", sync);
  ctx.on("pane.closed", sync);
  ctx.on("composer-vim:mode", sync);
  sync();
}
