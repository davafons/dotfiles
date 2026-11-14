import { remove, writeTextFile } from "yuke:fs";
import type { PluginContext, SessionInspection } from "yuke:plugins";
import { Command, env } from "yuke:process";
import { Transcript } from "yuke:transcript";
import { Picker, stack, TextView } from "yuke:tui";
import { command, currentSession } from "../../lib.ts";
import { markdown } from "../../views.ts";

type Bucket = {
  input: number;
  output: number;
  reasoning: number;
  cacheRead: number;
  cacheWrite: number;
  cost: number;
  withoutCache: number;
  messages: number;
  unpriced: number;
  unreported: number;
};
interface Chat {
  id: string;
  title: string;
  root: string;
  kind: string;
  input: number;
  output: number;
  messages: number;
}
interface Usage {
  totals: Bucket;
  daily: (Bucket & { date: string })[];
  models: (Bucket & { name: string })[];
  providers: (Bucket & { name: string })[];
  roles: Record<string, number>;
  finishes: Record<string, number>;
  outcomes: Record<string, number>;
  efforts: Record<string, number>;
  tools: { name: string; calls: number; errors: number; durationMs: number }[];
  skills: Record<string, number>;
  chats: Chat[];
  currentStreak: number;
  longestStreak: number;
  notes: string[];
}
const number = (value: number): string => value.toLocaleString("en-US");
const table = (value: Record<string, number>): string =>
  Object.entries(value)
    .map(([key, value]) => `| ${key} | ${number(value)} |`)
    .join("\n");
const bucket = (row: Bucket): string =>
  `${number(row.input)} input · ${number(row.output)} output · ${number(row.reasoning)} reasoning · ${number(row.cacheRead)} cache read · ${number(row.messages)} responses\n\nEstimated $${row.cost.toFixed(4)} · ${row.unpriced} unpriced · ${row.unreported} unreported`;

/** Inspect saved context, prompt previews, registered tools, usage, and provider allowances on demand. */
export function apply(ctx: PluginContext): undefined {
  const tui = ctx.get("tui");
  if (tui === undefined) return;
  const sessions = ctx.get("sessions"),
    chat = ctx.get("chat");
  const data = `${ctx.dataDir}/../..`;
  const helper = async <T>(name: string, args: readonly string[], signal: AbortSignal): Promise<T> => {
    const result = await new Command("python3", {
      args: [`${import.meta.dirname}/../../helpers/${name}.py`, ...args],
      cwd: ctx.dataDir,
      signal,
    }).output();
    if (!result.success) throw new Error(new TextDecoder().decode(result.stderr));
    return JSON.parse(new TextDecoder().decode(result.stdout)) as T;
  };
  for (const name of ["context", "status"] as const)
    command(
      ctx,
      tui,
      name,
      name === "context" ? "Inspect context, prompt sections, and tools" : "Show session usage and account allowances",
      async () => {
        const id = currentSession(ctx, tui);
        if (id === undefined) throw new Error("Open a saved session first.");
        let tab = 0,
          busy = false;
        let inspection: SessionInspection | undefined;
        let window: number | undefined;
        const view = new TextView({ document: markdown("inspection", "Reading…") });
        const render = (): void => {
          if (inspection === undefined) return;
          const info = inspection;
          if (tab === 0) {
            const encoder = new TextEncoder();
            const sections = info.prompt.map((section) => ({
              key: section.key,
              tokens: Math.ceil(encoder.encode(section.text).length / 4),
            }));
            const prompt = sections.reduce((total, section) => total + section.tokens, 0);
            const tools = info.tools.reduce(
              (total, tool) =>
                total +
                (tool.deferLoading
                  ? 0
                  : Math.ceil(encoder.encode(tool.name + tool.description + tool.inputSchema).length / 4)),
              0,
            );
            const used = info.contextTokens + (info.inputTokens === null ? prompt + tools : 0);
            const attributed = prompt + tools <= used;
            const share = window === undefined || window === 0 ? undefined : Math.min(1, used / window);
            const gauge =
              share === undefined
                ? ""
                : "■".repeat(Math.ceil(share * 40)) + "□".repeat(Math.max(0, 40 - Math.ceil(share * 40)));
            view.setDocument(
              markdown(
                "inspection",
                `# Context budget · estimates\n${gauge}\n\n≈${number(used)} tokens${window === undefined ? " · window unknown" : ` / ${number(window)} window · ${((used / window) * 100).toFixed(1)}%`}\n\n${info.inputTokens === null ? "No provider count yet. The estimate includes the prompt preview, registered non-deferred tools, and saved blocks." : `Last reported input: ${number(info.inputTokens)} tokens. Later saved blocks use the engine estimate. Prompt and tool attribution is approximate.`}\n\n| Part | Estimated tokens |\n| --- | ---: |\n${sections.map((section) => `| ${section.key} | ≈${number(section.tokens)} |`).join("\n")}\n| Registered tool schemas | ≈${number(tools)} |\n| ${attributed ? "Conversation, results, reasoning" : "Saved context · attribution unavailable"} | ≈${number(attributed ? used - prompt - tools : used)} |\n${window === undefined ? "" : `| Window remaining | ≈${number(Math.max(0, window - used))} |`}\n\nCached input still occupies context. Live drafts and queued input are excluded. The current prompt preview can differ from the last request, and round hooks can offer fewer tools.\n\nTab shows saved blocks, prompt sections, and complete tool schemas.`,
              ),
            );
          } else if (tab === 2)
            view.setDocument(
              markdown(
                "inspection",
                `# Prompt preview\nPrompt hooks run now. Round hooks do not run.\n\n${info.prompt.map((section) => `## ${section.key}\n${section.text}`).join("\n\n")}`,
              ),
            );
          else if (tab === 3)
            view.setDocument(
              markdown(
                "inspection",
                `# Registered tools\nBefore round hooks choose a subset. This view runs no handler.\n\n${info.tools.map((tool) => `## ${tool.name}\n${tool.description}\n\n\`\`\`json\n${JSON.stringify(JSON.parse(tool.inputSchema), null, 2)}\n\`\`\``).join("\n\n")}`,
              ),
            );
          else
            view.setDocument(
              markdown(
                "inspection",
                `# Saved context\nLive drafts and pending input stay outside this snapshot.\n\n${info.context.map((block, index) => `## Block ${index + 1}\n\`\`\`json\n${JSON.stringify(block, null, 2)}\n\`\`\``).join("\n\n")}`,
              ),
            );
          view.scroll.scrollTo(0);
          tui.requestFrame();
        };
        const refresh = async (): Promise<void> => {
          if (busy) return;
          busy = true;
          try {
            inspection = await sessions.inspect(id);
            if (dialog.signal.aborted) return;
            if (name === "context") {
              const provider = (await ctx.get("catalog").list({ all: true })).providers.find(
                (provider) => provider.id === inspection?.settings.model.provider,
              );
              window =
                provider?.models.find((model) => model.id === inspection?.settings.model.model)?.contextWindow ??
                undefined;
              render();
              return;
            }
            const transcript = new Transcript();
            const hold = new AbortController();
            try {
              await sessions.open(id, {
                tail: 200,
                signal: AbortSignal.any([dialog.signal, hold.signal]),
                onEvent: (event) => transcript.apply(event),
              });
            } finally {
              hold.abort();
            }
            const provider = (await ctx.get("catalog").list({ all: true })).providers.find(
              (row) => row.id === inspection?.settings.model.provider,
            );
            const model = provider?.models.find((row) => row.id === inspection?.settings.model.model);
            const configHome = env.get("XDG_CONFIG_HOME") || `${env.get("HOME")}/.config`;
            const config = `${configHome}/${env.get("YUKE_APPNAME") || "yuke"}`;
            const quota = await helper<{
              state: string;
              error: string;
              plan: string;
              windows: { label: string; remainingPercent: number; resetsAt: number | null }[];
              notes: string[];
              creditBalance: number | null;
            }>("status-data", [inspection.settings.model.provider, "--config", config, "--data", data], dialog.signal);
            if (dialog.signal.aborted) return;
            const usage = transcript.usage;
            const used = usage?.input;
            const sections = inspection.prompt
              .map(
                (section) =>
                  `| ${section.key} | ${new TextEncoder().encode(section.text).length} bytes | ≈${Math.ceil(section.text.length / 4)} tokens |`,
              )
              .join("\n");
            view.setDocument(
              markdown(
                "inspection",
                `# Status\n${tui.startup.version}\n\n${inspection.settings.model.provider}/${inspection.settings.model.model}\n${inspection.settings.cwd}\n\n${transcript.state} · ${transcript.pending.size} queued · ${transcript.interactions.size} interactions\n\nContext: ${used == null ? "unknown" : number(used)} last reported input tokens / ${model?.contextWindow == null ? "unknown" : number(model.contextWindow)} window\nLast response: ${usage?.output == null ? "unknown" : number(usage.output)} output tokens\nRegistered tools: ${inspection.tools.length}\n\n## Prompt preview · size estimates\n| Section | Bytes | Tokens |\n| --- | ---: | ---: |\n${sections}\n\n## Account allowance\n${quota.plan}\n${quota.error}\n${quota.windows.map((window) => `${window.label}: ${window.remainingPercent.toFixed(1)}% remaining${window.resetsAt === null ? "" : ` · resets ${new Date(window.resetsAt * 1000).toLocaleString()}`}`).join("\n\n")}\n${quota.creditBalance === null ? "" : `Credits: ${quota.creditBalance}`}\n${quota.notes.join("\n\n")}`,
              ),
            );
            tui.requestFrame();
          } finally {
            busy = false;
          }
        };
        const dialog = tui.dialog({
          title: () =>
            name === "context"
              ? `Context · ${["budget", "saved blocks", "prompt preview", "registered tools"][tab]}`
              : "Status",
          body: view,
          rows: Math.max(10, tui.size.height - 2),
          keys: [
            {
              key: "tab",
              label: "next view",
              when: () => name === "context",
              run: () => {
                tab = (tab + 1) % 4;
                render();
              },
            },
            {
              key: "ctrl+r",
              label: "refresh",
              run: () => {
                void refresh().catch((error: unknown) => ctx.notify("error", String(error)));
              },
            },
            ...(["j", "k", "down", "up", "pagedown", "pageup"] as const).map((key) => ({
              key,
              label: "scroll",
              run: () =>
                view.scroll.scrollBy(
                  (key === "j" || key === "down" || key === "pagedown" ? 1 : -1) * (key.startsWith("page") ? 12 : 1),
                ),
            })),
          ],
        });
        await refresh();
      },
    );
  command(ctx, tui, "usage", "Browse usage by day, model, tool, skill, and chat", async () => {
    let tab = 0,
      period = 0,
      all = true,
      busy = false;
    let usage: Usage | undefined;
    const cwd =
      tui.panes.active === undefined ? tui.startup.cwd : (chat.folder(tui.panes.active.view) ?? tui.startup.cwd);
    const view = new TextView({ document: markdown("usage", "Reading…") });
    const picker = new Picker<Chat>({
      items: [],
      id: (row) => row.id,
      label: (row) => row.title,
      detail: (row) => `${row.root} · ${row.messages} responses`,
      onChoose: (row) => {
        void ctx
          .get("personal-navigation")
          .openSession(row.id)
          .then(
            () => dialog.close(),
            (error: unknown) => ctx.notify("error", String(error)),
          );
      },
      onCancel: () => dialog.close(),
    });
    const render = (): void => {
      if (usage === undefined) return;
      const value = usage;
      let text = "";
      if (tab === 0)
        text = `${bucket(value.totals)}\n\n${value.chats.filter((row) => row.kind === "chat").length} chats · ${value.chats.filter((row) => row.kind === "child").length} children\nStreak: ${value.currentStreak} days · longest ${value.longestStreak}\n\n${value.notes.join("\n\n")}`;
      else if (tab === 1) {
        const days = new Map<string, { input: number; output: number; cost: number }>();
        for (const day of value.daily) {
          const date = new Date(`${day.date}T12:00:00`);
          if (period === 1) date.setDate(date.getDate() - ((date.getDay() + 6) % 7));
          const key =
            period === 2
              ? day.date.slice(0, 7)
              : period === 1
                ? `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`
                : day.date;
          const row = days.get(key) ?? { input: 0, output: 0, cost: 0 };
          row.input += day.input;
          row.output += day.output;
          row.cost += day.cost;
          days.set(key, row);
        }
        text = `## ${["Daily", "Weekly", "Monthly"][period]}\n| Period | Input | Output | Estimated cost |\n| --- | ---: | ---: | ---: |\n${[
          ...days,
        ]
          .toReversed()
          .map(([key, row]) => `| ${key} | ${number(row.input)} | ${number(row.output)} | $${row.cost.toFixed(4)} |`)
          .join(
            "\n",
          )}\n\n## Models\n${value.models.map((row) => `### ${row.name}\n${bucket(row)}`).join("\n\n")}\n\n## Providers\n${value.providers.map((row) => `### ${row.name}\n${bucket(row)}`).join("\n\n")}`;
      } else if (tab === 2)
        text = `## Block kinds\n| Kind | Count |\n| --- | ---: |\n${table(value.roles)}\n\n## Outcomes\n| Outcome | Count |\n| --- | ---: |\n${table(value.outcomes)}\n\n## Finish reasons\n| Finish | Count |\n| --- | ---: |\n${table(value.finishes)}\n\n## Effort\n| Effort | Count |\n| --- | ---: |\n${table(value.efforts)}`;
      else if (tab === 3)
        text = `## Tool calls\n| Tool | Calls | Errors |\n| --- | ---: | ---: |\n${value.tools.map((row) => `| ${row.name} | ${row.calls} | ${row.errors} |`).join("\n")}`;
      else if (tab === 4) text = `## Admitted skills\n| Skill | Invocations |\n| --- | ---: |\n${table(value.skills)}`;
      view.setDocument(
        markdown("usage", `# ${["Overview", "Usage", "Messages", "Plugins", "Skills", "Chats"][tab]}\n${text}`),
      );
      picker.setItems(tab === 5 ? value.chats : []);
      view.scroll.scrollTo(0);
      tui.requestFrame();
    };
    const refresh = async (): Promise<void> => {
      if (busy) return;
      busy = true;
      const path = `${ctx.dataDir}/usage-request-${Date.now()}.json`;
      try {
        await writeTextFile(
          path,
          JSON.stringify({
            database: `${data}/yuke.db`,
            workspace: all ? null : cwd,
            providers: (await ctx.get("catalog").list({ all: true })).providers,
          }),
          { createNew: true, mode: 0o600 },
        );
        usage = await helper<Usage>("usage-rust", [path], dialog.signal);
        if (!dialog.signal.aborted) render();
      } finally {
        await remove(path, { force: true });
        busy = false;
      }
    };
    const failed = (error: unknown): void => ctx.notify("error", String(error));
    const choose = (index: number): void => {
      tab = index;
      render();
      tui.focus(tab === 5 ? picker : view);
    };
    const dialog = tui.dialog({
      title: () => `Usage · ${all ? "all workspaces" : cwd}`,
      body: {
        ...stack("column", [
          { view, size: (size) => (tab === 5 ? 0 : size.height) },
          { view: picker, size: (size) => (tab === 5 ? size.height : 0) },
        ]),
        initialFocus: view,
      },
      rows: Math.max(10, tui.size.height - 2),
      keys: [
        ...Array.from({ length: 6 }, (_, index) => ({
          key: `alt+${index + 1}`,
          label: ["overview", "usage", "messages", "plugins", "skills", "chats"][index] ?? "",
          run: () => choose(index),
        })),
        { key: "tab", label: "next tab", run: () => choose((tab + 1) % 6) },
        {
          key: "ctrl+r",
          label: "refresh",
          run: () => {
            void refresh().catch(failed);
          },
        },
        {
          key: "alt+w",
          label: "workspace/all",
          when: () => !busy,
          run: () => {
            all = !all;
            void refresh().catch(failed);
          },
        },
        {
          key: "g",
          label: "period",
          when: () => tab !== 5,
          run: () => {
            period = (period + 1) % 3;
            render();
          },
        },
        { key: "j", label: "down", when: () => tab !== 5, run: () => view.scroll.scrollBy(1) },
        { key: "k", label: "up", when: () => tab !== 5, run: () => view.scroll.scrollBy(-1) },
        { key: "pagedown", label: "page down", run: () => view.scroll.scrollBy(12) },
        { key: "pageup", label: "page up", run: () => view.scroll.scrollBy(-12) },
      ],
    });
    await refresh();
  });
}
