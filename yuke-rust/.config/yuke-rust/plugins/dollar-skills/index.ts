import { readTextFile } from "yuke:fs";
import type { PluginContext, SessionContext, SessionHooks } from "yuke:plugins";
import { Command } from "yuke:process";
import type { Block } from "yuke:protocol";
import { TextEditor } from "yuke:tui";
import { Completion } from "../../completion.ts";
import type {} from "../vim/src/service.ts";

interface Skill {
  readonly name: string;
  readonly description: string;
  readonly path: string;
  readonly canonical_path: string;
}
const catalogs = new Map<string, Promise<readonly Skill[]>>();

/** Find explicit skill mentions outside code spans. Escaped dollar signs stay literal. */
export function mentions(text: string): string[] {
  const names: string[] = [];
  const pattern = /(`+)[\s\S]*?\1|\\\$|(^|\s)\$([a-z0-9]+(?:-[a-z0-9]+)*)(?=$|[^\w$-])/g;
  for (const match of text.matchAll(pattern)) if (match[3] !== undefined) names.push(match[3]);
  return names;
}

function scan(folder: string, signal: AbortSignal): Promise<readonly Skill[]> {
  let catalog = catalogs.get(folder);
  if (catalog === undefined) {
    catalog = new Command("python3", {
      args: [`${import.meta.dirname}/../../helpers/dollar-skills.py`, "scan", folder],
      cwd: folder,
      signal,
    })
      .output()
      .then((output) => {
        const decoder = new TextDecoder();
        if (!output.success) throw new Error(decoder.decode(output.stderr));
        return JSON.parse(decoder.decode(output.stdout)) as Skill[];
      });
    catalogs.set(folder, catalog);
    catalog.catch(() => {
      if (catalogs.get(folder) === catalog) catalogs.delete(folder);
    });
  }
  return catalog;
}

/** Expand all named skills for the model while retaining the exact user input in the transcript. */
export function session(s: SessionContext): undefined {
  const expand: SessionHooks["input.before"] = async (event) => {
    const names = new Set<string>();
    for (const block of event.blocks)
      if ("user_text" in block && block.user_text.includes("$"))
        for (const name of mentions(block.user_text)) names.add(name);
    if (names.size === 0) return undefined;
    const selected = (await scan(s.folder, s.signal)).filter((skill) => names.has(skill.name));
    if (selected.length === 0) return undefined;
    const bodies: Block[] = [];
    for (const skill of selected) {
      const source = await readTextFile(skill.canonical_path, { signal: event.signal });
      const body = source.replace(/^---\r?\n[\s\S]*?\r?\n---(?:\r?\n|$)/, "").trim();
      bodies.push({
        user_text: `<skill name=${JSON.stringify(skill.name)} path=${JSON.stringify(skill.path)}>\n${body}\n</skill>`,
      });
    }
    const [first, ...rest] = [...event.blocks, ...bodies];
    return first === undefined ? undefined : { replace: { blocks: [first, ...rest] } };
  };
  s.hook("input.before", (event) => {
    if (event.source.kind !== "user") return undefined;
    for (let index = 0; index < event.blocks.length; index += 1) {
      const block = event.blocks[index];
      if (block !== undefined && "user_text" in block && block.user_text.includes("$")) return expand(event);
    }
    return undefined;
  });
}

/** Complete skill names in each composer. A modal or Vim mode change closes the list. */
export function apply(ctx: PluginContext): undefined {
  const tui = ctx.get("tui");
  const vim = ctx.get("composer-vim");
  if (tui === undefined || vim === undefined) return;
  tui.widgets.watch((mount) => {
    const editor = mount.widget;
    if (!(editor instanceof TextEditor) || editor.role !== "composer") return;
    const extension = editor.extend(mount.signal);
    let list: Completion<Skill> | undefined;
    let generation = 0;
    let dismissedText: string | undefined;
    let dismissedCaret = -1;
    const close = (): void => {
      list?.close();
      list = undefined;
      generation += 1;
    };
    const sync = (): void => {
      close();
      const source = editor.state;
      const caret = editor.caret;
      if (
        tui.focused !== editor ||
        vim.mode(editor) !== "insert" ||
        (dismissedText === source.text && dismissedCaret === caret)
      )
        return;
      const prefix = source.text.slice(0, caret);
      const match = /(?:^|\s)\$([a-z0-9-]*)$/.exec(prefix);
      if (match?.[1] === undefined || prefix.replace(/(`+)[\s\S]*?\1/g, "").includes("`")) return;
      void complete(source, caret, match[1], generation).catch(failed);
    };
    const complete = async (
      source: import("yuke:tui").EditorState,
      caret: number,
      query: string,
      serial: number,
    ): Promise<void> => {
      const folder =
        mount.pane === undefined ? tui.startup.cwd : (ctx.get("chat").folder(mount.pane.view) ?? tui.startup.cwd);
      const matches = (await scan(folder, ctx.signal)).filter((skill) => skill.name.startsWith(query));
      if (
        generation !== serial ||
        ctx.signal.aborted ||
        mount.signal.aborted ||
        editor.state !== source ||
        tui.focused !== editor ||
        matches.length === 0
      )
        return;
      list = new Completion(
        tui,
        mount,
        matches,
        (skill) => `$${skill.name}  ${skill.description.replace(/\s+/g, " ")}`,
        (skill) => {
          let end = caret;
          while (end < source.text.length && /[a-z0-9-]/.test(source.text[end] ?? "")) end += 1;
          close();
          editor.replace(caret - query.length - 1, end, `$${skill.name} `);
        },
        () => {
          dismissedText = source.text;
          dismissedCaret = caret;
          close();
        },
      );
    };
    const failed = (error: unknown): void => {
      if (!ctx.signal.aborted && !mount.signal.aborted) ctx.notify("error", String(error));
    };
    const refresh = sync;
    extension.onChange(refresh);
    const stopFocus = tui.onFocus(() => {
      if (tui.focused !== editor) close();
    });
    const stopMode = vim.onMode((changed) => {
      if (changed === editor) refresh();
    });
    return () => {
      close();
      extension.dispose();
      stopFocus();
      stopMode();
    };
  });
}
