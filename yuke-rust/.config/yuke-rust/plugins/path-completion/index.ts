import { type DirEntry, readDir, stat } from "yuke:fs";
import type { PluginContext } from "yuke:plugins";
import { env } from "yuke:process";
import { TextEditor } from "yuke:tui";
import { Completion } from "../../completion.ts";
import type {} from "../vim/src/service.ts";
import { type PathWord, pathWord } from "./word.ts";

/** Complete file and directory paths at the caret. Missing directories close the list. Other failures produce a notice. */
export function apply(ctx: PluginContext): undefined {
  const tui = ctx.get("tui");
  const vim = ctx.get("composer-vim");
  if (tui === undefined || vim === undefined) return;
  tui.widgets.watch((mount) => {
    const editor = mount.widget;
    if (!(editor instanceof TextEditor) || editor.role !== "composer") return;
    const extension = editor.extend(mount.signal);
    let list: Completion<DirEntry> | undefined;
    let generation = 0;
    let dismissedText: string | undefined;
    let dismissedCaret = -1;
    let heldDirectory = "";
    let entries: DirEntry[] = [];
    const close = (): void => {
      list?.close();
      list = undefined;
      generation += 1;
    };
    const sync = (): void => {
      close();
      const text = editor.state.text;
      const caret = editor.caret;
      if (
        tui.focused !== editor ||
        vim.mode(editor) !== "insert" ||
        (dismissedText === text && dismissedCaret === caret)
      )
        return;
      const word = pathWord(text, caret);
      if (word === null) return;
      void load(text, caret, word, generation).catch(failed);
    };
    const load = async (text: string, caret: number, word: PathWord, serial: number): Promise<void> => {
      const folder =
        mount.pane === undefined ? tui.startup.cwd : (ctx.get("chat").folder(mount.pane.view) ?? tui.startup.cwd);
      const directory = word.directory.startsWith("~/")
        ? `${env.get("HOME")}${word.directory.slice(1)}`
        : word.directory;
      const key = `${folder}:${directory}`;
      if (heldDirectory !== key) {
        const found = await readDir(directory, { baseDir: folder, signal: ctx.signal });
        for (const entry of found) {
          if (!entry.isSymlink) continue;
          const info = await stat(`${directory}${entry.name}`, { baseDir: folder, signal: ctx.signal });
          entry.isDirectory = info.isDirectory;
          entry.isFile = info.isFile;
        }
        if (generation !== serial) return;
        heldDirectory = key;
        entries = found.sort(
          (left, right) => Number(right.isDirectory) - Number(left.isDirectory) || left.name.localeCompare(right.name),
        );
      }
      if (
        ctx.signal.aborted ||
        mount.signal.aborted ||
        generation !== serial ||
        editor.state.text !== text ||
        editor.caret !== caret ||
        tui.focused !== editor ||
        vim.mode(editor) !== "insert"
      )
        return;
      const directoriesOnly = /^\/cd[ \t]/.test(text);
      const matches = entries.filter(
        (entry) =>
          !/[\r\n]/.test(entry.name) &&
          entry.name.startsWith(word.prefix) &&
          (!entry.name.startsWith(".") || word.prefix.startsWith(".")) &&
          (!directoriesOnly || entry.isDirectory),
      );
      if (matches.length === 0) return;
      const complete = (entry: DirEntry): void => {
        if (editor.state.text !== text || editor.caret !== caret) {
          close();
          return;
        }
        let replacement = `${word.directory}${entry.name}${entry.isDirectory ? "/" : ""}`;
        let closedQuote = false;
        if (word.quote !== "" && word.to === text.length && directoriesOnly) {
          replacement += word.quote;
          closedQuote = true;
        }
        if (word.quote === "" && /[\s"'`]/.test(replacement)) {
          const quote = !replacement.includes('"') ? '"' : !replacement.includes("'") ? "'" : "`";
          replacement = `${quote}${replacement}${quote}`;
          closedQuote = true;
        }
        close();
        editor.replace(word.from, word.to, replacement);
        if (entry.isDirectory && closedQuote) editor.caret -= 1;
        if (!entry.isDirectory) {
          dismissedText = editor.state.text;
          dismissedCaret = editor.caret;
        } else sync();
      };
      list = new Completion(
        tui,
        mount,
        matches,
        (entry) => `${entry.name}${entry.isDirectory ? "/" : ""}`,
        complete,
        () => {
          dismissedText = text;
          dismissedCaret = caret;
          close();
        },
      );
    };
    const failed = (error: unknown): void => {
      if (ctx.signal.aborted || mount.signal.aborted) return;
      close();
      if (!(error instanceof Error && "code" in error && (error.code === "ENOENT" || error.code === "ENOTDIR")))
        ctx.notify("error", String(error));
    };
    extension.onChange(() => {
      sync();
    });
    const stopMode = vim.onMode((changed) => {
      if (changed === editor) sync();
    });
    const stopFocus = tui.onFocus(() => {
      if (tui.focused !== editor) close();
      else sync();
    });
    return () => {
      close();
      extension.dispose();
      stopMode();
      stopFocus();
    };
  });
}
