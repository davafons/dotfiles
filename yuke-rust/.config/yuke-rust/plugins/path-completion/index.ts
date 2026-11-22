import type { CompletionItem } from "yuke:chat";
import { type DirEntry, readDir, stat } from "yuke:fs";
import type { PluginContext } from "yuke:plugins";
import { env } from "yuke:process";
import { focusedEditor } from "../../lib.ts";
import type {} from "../vim/src/service.ts";
import { pathWord } from "./word.ts";

/**
 * Complete file and directory paths at the caret, in Vim Insert mode. `/cd` lists only directories.
 * A missing directory gives no list. Other read failures produce a notice.
 */
export function apply(ctx: PluginContext): undefined {
  const tui = ctx.get("tui");
  const vim = ctx.get("composer-vim");
  if (tui === undefined || vim === undefined) return;
  let held = "";
  let entries: DirEntry[] = [];
  const list = async (folder: string, directory: string, signal: AbortSignal): Promise<DirEntry[]> => {
    const key = `${folder}:${directory}`;
    if (held === key) return entries;
    const found: DirEntry[] = [];
    for await (const entry of readDir(directory, { folder: folder, signal })) {
      if (entry.isSymlink) {
        const info = await stat(`${directory}${entry.name}`, { folder: folder, signal });
        entry.isDirectory = info.isDirectory;
        entry.isFile = info.isFile;
      }
      found.push(entry);
    }
    found.sort(
      (left, right) => Number(right.isDirectory) - Number(left.isDirectory) || left.name.localeCompare(right.name),
    );
    held = key;
    entries = found;
    return found;
  };
  const remove = ctx.get("chat").addCompletionProvider({
    complete: async (context) => {
      const editor = focusedEditor(tui);
      if (editor === undefined || vim.mode(editor) !== "insert") return undefined;
      const { text, caret } = context;
      const word = pathWord(text, caret);
      if (word === null) return undefined;
      const directory = word.directory.startsWith("~/")
        ? `${env.get("HOME")}${word.directory.slice(1)}`
        : word.directory;
      let found: DirEntry[];
      try {
        found = await list(context.folder, directory, context.signal);
      } catch (error) {
        if (context.signal.aborted) return undefined;
        if (!(error instanceof Error && "code" in error && (error.code === "ENOENT" || error.code === "ENOTDIR")))
          ctx.notify("error", String(error));
        return undefined;
      }
      const directoriesOnly = /^\/cd[ \t]/.test(text);
      const matches = found.filter(
        (entry) =>
          !/[\r\n]/.test(entry.name) &&
          entry.name.startsWith(word.prefix) &&
          (!entry.name.startsWith(".") || word.prefix.startsWith(".")) &&
          (!directoriesOnly || entry.isDirectory),
      );
      // A completed file name matches only itself. The list then ends instead of offering it again.
      if (matches.length === 1 && !matches[0]?.isDirectory && matches[0]?.name === word.prefix) return undefined;
      const items: CompletionItem[] = matches.map((entry) => {
        let insert = `${word.directory}${entry.name}${entry.isDirectory ? "/" : ""}`;
        // A file, or a /cd target, closes its quote. Another directory leaves it open so the next level completes in place.
        const close = !entry.isDirectory || directoriesOnly;
        if (word.quote === "" && /[\s"'`]/.test(insert)) {
          const quote = !insert.includes('"') ? '"' : !insert.includes("'") ? "'" : "`";
          insert = `${quote}${insert}${close ? quote : ""}`;
        } else if (word.quote !== "" && close && word.to === caret) insert += word.quote;
        return { label: `${entry.name}${entry.isDirectory ? "/" : ""}`, insert };
      });
      return items.length === 0 ? undefined : { from: word.from, to: word.to, items };
    },
  });
  ctx.signal.addEventListener("abort", remove, { once: true });
}
