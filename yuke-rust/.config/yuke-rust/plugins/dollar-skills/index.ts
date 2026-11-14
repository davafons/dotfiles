import { readTextFile } from "yuke:fs";
import type { PluginContext, SessionContext, SessionHooks } from "yuke:plugins";
import { Command } from "yuke:process";
import type { Block } from "yuke:protocol";
import { focusedEditor } from "../../lib.ts";
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
      if ("kind" in block && block.kind === "userText" && block.text.includes("$"))
        for (const name of mentions(block.text)) names.add(name);
    if (names.size === 0) return undefined;
    const selected = (await scan(s.cwd, s.signal)).filter((skill) => names.has(skill.name));
    if (selected.length === 0) return undefined;
    const bodies: Block[] = [];
    for (const skill of selected) {
      const source = await readTextFile(skill.canonical_path, { signal: event.signal });
      const body = source.replace(/^---\r?\n[\s\S]*?\r?\n---(?:\r?\n|$)/, "").trim();
      bodies.push({
        kind: "userText",
        text: `<skill name=${JSON.stringify(skill.name)} path=${JSON.stringify(skill.path)}>\n${body}\n</skill>`,
      });
    }
    const [first, ...rest] = [...event.blocks, ...bodies];
    return first === undefined ? undefined : { replace: { blocks: [first, ...rest] } };
  };
  s.addHook("input.before", (event) => {
    if (event.source.kind !== "user") return undefined;
    for (let index = 0; index < event.blocks.length; index += 1) {
      const block = event.blocks[index];
      if (block !== undefined && "kind" in block && block.kind === "userText" && block.text.includes("$"))
        return expand(event);
    }
    return undefined;
  });
}

/** Complete skill names after `$` in Vim Insert mode, outside code spans. */
export function apply(ctx: PluginContext): undefined {
  const tui = ctx.get("tui");
  const vim = ctx.get("composer-vim");
  if (tui === undefined || vim === undefined) return;
  const remove = ctx.get("chat").addCompletionProvider({
    complete: async (context) => {
      const editor = focusedEditor(tui);
      if (editor === undefined || vim.mode(editor) !== "insert") return undefined;
      const prefix = context.text.slice(0, context.caret);
      const match = /(?:^|\s)\$([a-z0-9-]*)$/.exec(prefix);
      const query = match?.[1];
      if (query === undefined || prefix.replace(/(`+)[\s\S]*?\1/g, "").includes("`")) return undefined;
      let skills: readonly Skill[];
      try {
        skills = await scan(context.cwd, ctx.signal);
      } catch (error) {
        if (!ctx.signal.aborted && !context.signal.aborted) ctx.notify("error", String(error));
        return undefined;
      }
      let to = context.caret;
      while (to < context.text.length && /[a-z0-9-]/.test(context.text[to] ?? "")) to += 1;
      const items = skills
        .filter((skill) => skill.name.startsWith(query))
        .map((skill) => ({
          label: `$${skill.name}`,
          detail: skill.description.replace(/\s+/g, " "),
          insert: `$${skill.name} `,
        }));
      return items.length === 0 ? undefined : { from: context.caret - query.length - 1, to, items };
    },
  });
  ctx.signal.addEventListener("abort", remove, { once: true });
}
