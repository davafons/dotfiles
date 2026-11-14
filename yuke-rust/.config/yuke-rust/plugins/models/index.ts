import type { ChatModelChoice, ChatModelPickerContext } from "yuke:chat";
import { FileSystemError, readTextFile } from "yuke:fs";
import type { PluginContext } from "yuke:plugins";
import { Command } from "yuke:process";
import type { ModelInfo, ProviderInfo } from "yuke:protocol";
import type { Infer } from "yuke:tools";
import { TextEditor } from "yuke:tui";
import { command } from "../../lib.ts";

export const optionsSchema = {
  type: "object",
  properties: {
    startupModel: { type: "string" },
    startupEffort: { type: "string" },
    picker: { type: "boolean" },
    effortPicker: { type: "boolean" },
    aliases: { type: "boolean" },
    modelKey: { type: "string" },
    effortKey: { type: "string" },
  },
} as const;

interface Preset {
  readonly alias: string;
  readonly model?: string;
  readonly latest?: { readonly provider: string; readonly family: "sol" | "luna" };
  readonly effort?: string;
  readonly key?: string;
}
interface Aliases {
  readonly version: 1;
  readonly revision: number;
  readonly presets: readonly Preset[];
}
interface Row {
  readonly provider: string;
  readonly model: ModelInfo;
}

/** Resolve an exact selector or the newest numeric version in a model family. */
export function resolve(preset: Preset, providers: readonly ProviderInfo[]): Row | undefined {
  const rows = providers.flatMap((provider) => provider.models.map((model) => ({ provider: provider.id, model })));
  if (preset.latest === undefined) return rows.find((row) => `${row.provider}/${row.model.id}` === preset.model);
  const family = preset.latest;
  const pattern = new RegExp(`^gpt-(\\d+(?:\\.\\d+)*)-${family.family}$`);
  return rows
    .filter((row) => row.provider === family.provider && pattern.test(row.model.id))
    .sort((a, b) => {
      const left = a.model.id.split("-")[1]?.split(".").map(Number) ?? [];
      const right = b.model.id.split("-")[1]?.split(".").map(Number) ?? [];
      for (let index = 0; index < Math.max(left.length, right.length); index += 1) {
        const difference = (right[index] ?? 0) - (left[index] ?? 0);
        if (difference !== 0) return difference;
      }
      return 0;
    })[0];
}

/** Install the model picker, effort picker, alias commands, and alias editor. Invalid alias files fail to load. */
export async function apply(ctx: PluginContext<Infer<typeof optionsSchema>>): Promise<undefined> {
  const tui = ctx.get("tui");
  if (tui === undefined) return;
  const file = `${ctx.dataDir}/model-aliases.json`;
  let aliases: Aliases = {
    version: 1,
    revision: 0,
    presets: [
      { alias: "sh", latest: { provider: "openai-codex", family: "sol" }, effort: "high", key: "ctrl+x s" },
      { alias: "lm", latest: { provider: "openai-codex", family: "luna" }, effort: "medium", key: "ctrl+x l" },
    ],
  };
  const validate = async (value: unknown): Promise<Aliases> => {
    const output = await new Command("python3", {
      args: [
        "-c",
        "import importlib.util,json,sys; p=importlib.util.spec_from_file_location('aliases',sys.argv[1]); m=importlib.util.module_from_spec(p); p.loader.exec_module(m); print(json.dumps(m.validate(json.loads(sys.argv[2]))))",
        `${import.meta.dirname}/../../helpers/model-alias-store.py`,
        JSON.stringify(value),
      ],
      cwd: ctx.dataDir,
      signal: ctx.signal,
    }).output();
    if (!output.success) throw new Error(new TextDecoder().decode(output.stderr));
    return JSON.parse(new TextDecoder().decode(output.stdout)) as Aliases;
  };
  try {
    aliases = await validate(JSON.parse(await readTextFile(file, { signal: ctx.signal })));
  } catch (error) {
    if (!(error instanceof FileSystemError && error.code === "ENOENT")) throw error;
  }
  const chat = ctx.get("chat");

  const pick = async (
    context: ChatModelPickerContext,
    query = "",
    effortOnly = false,
  ): Promise<ChatModelChoice | undefined> => {
    const providers = context.providers;
    let row: Row | undefined;
    let level: string | undefined;
    const current = context.current?.model ?? context.saved?.model;
    if (effortOnly) {
      row = providers
        .flatMap((provider) => provider.models.map((model) => ({ provider: provider.id, model })))
        .find((entry) => entry.provider === current?.provider && entry.model.id === current.model);
      level = query || undefined;
    } else if (query !== "") {
      const preset = aliases.presets.find((entry) => entry.alias === query);
      row = resolve(preset ?? { alias: query, model: query }, providers);
      level = preset?.effort;
      if (row === undefined) throw new Error(`No model matches ${query}`);
    }
    if (row === undefined) {
      const models = providers.flatMap((provider) =>
        provider.models.map((model) => ({ provider: provider.id, model })),
      );
      row = await tui.select({
        title: "Model",
        items: models,
        label: (entry) => `${entry.provider}/${entry.model.id}`,
        signal: context.signal,
      });
    }
    if (row === undefined) return undefined;
    let reasoning = level === undefined ? undefined : row.model.reasoning.find((entry) => entry.level === level);
    if (level !== undefined && reasoning === undefined) throw new Error(`${row.model.id} has no ${level} effort`);
    if (reasoning === undefined)
      reasoning = await tui.select({
        title: `${row.model.name} · effort`,
        items: row.model.reasoning,
        label: (entry) => entry.level,
        signal: context.signal,
      });
    return reasoning === undefined
      ? undefined
      : { model: { provider: row.provider, model: row.model.id }, reasoning: reasoning.level };
  };
  const stopPicker = ctx.options.picker === false ? undefined : chat.setModelPicker((context) => pick(context));
  const startupModel = ctx.options.startupModel ?? "",
    startupEffort = ctx.options.startupEffort ?? "";
  if ((startupModel === "") !== (startupEffort === "")) throw new Error("Set startupModel and startupEffort together.");
  if (startupModel !== "") {
    let started = false;
    tui.widgets.addWatcher((mount) => {
      if (started || mount.widget.role !== "composer") return;
      started = true;
      tui.addTimer(0, () => {
        void chat
          .chooseModel(async (context) => {
            const row = resolve({ alias: "startup", model: startupModel }, context.providers);
            const level = row?.model.reasoning.find((choice) => choice.level === startupEffort);
            if (row === undefined || level === undefined) {
              ctx.notify("warn", "The startup model or effort is unavailable. Keeping the saved default.");
              return undefined;
            }
            return { model: { provider: row.provider, model: row.model.id }, reasoning: level.level };
          })
          .catch((error: unknown) => ctx.notify("error", String(error)));
      });
      return undefined;
    });
  }
  if (stopPicker !== undefined) ctx.signal.addEventListener("abort", stopPicker, { once: true });
  if (ctx.options.picker !== false) {
    command(
      ctx,
      tui,
      "model",
      "Choose a model or alias",
      (query) => chat.chooseModel((context) => pick(context, query.trim())),
      "[model]",
    );
    tui.keys.add(ctx.options.modelKey ?? "ctrl+x m", "model", { in: "chat" });
  }
  if (ctx.options.effortPicker !== false) {
    command(
      ctx,
      tui,
      "effort",
      "Choose the reasoning effort",
      (query) => chat.chooseModel((context) => pick(context, query.trim(), true)),
      "[level]",
    );
    tui.keys.add(ctx.options.effortKey ?? "ctrl+x e", "effort", { in: "chat" });
  }
  if (ctx.options.aliases === false) return;
  for (const preset of aliases.presets) {
    command(ctx, tui, preset.alias, `Use ${preset.alias}`, () =>
      chat.chooseModel((context) => pick(context, preset.alias)),
    );
    if (preset.key !== undefined) tui.keys.add(preset.key, preset.alias, { in: "chat" });
  }
  command(ctx, tui, "model-aliases", "Edit persistent model aliases", () => {
    const editor = new TextEditor({
      state: { text: JSON.stringify(aliases, null, 2), selection: { anchor: 0, head: 0 }, spans: [] },
    });
    let saving = false;
    const dialog = tui.dialog({
      title: () => "Model aliases · Ctrl+S saves · reload applies keys",
      body: editor,
      rows: 20,
      keys: [
        {
          key: "ctrl+s",
          label: "save",
          when: () => !saving,
          run: () => {
            saving = true;
            Promise.resolve()
              .then(() => validate(JSON.parse(editor.state.text)))
              .then(async (value) => {
                const output = await new Command("python3", {
                  args: [`${import.meta.dirname}/../../helpers/model-alias-store.py`, file, JSON.stringify(value)],
                  cwd: ctx.dataDir,
                  signal: dialog.signal,
                }).output();
                if (!output.success) throw new Error(new TextDecoder().decode(output.stderr));
                aliases = await validate(JSON.parse(await readTextFile(file)));
                dialog.close();
                ctx.notify("info", "Model aliases saved. Run /reload to apply command and key changes.");
              })
              .catch((error: unknown) => ctx.notify("error", String(error)))
              .finally(() => {
                saving = false;
              });
          },
        },
      ],
    });
  });
}
