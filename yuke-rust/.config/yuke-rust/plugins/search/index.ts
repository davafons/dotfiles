import { remove, writeTextFile } from "yuke:fs";
import type { PluginContext } from "yuke:plugins";
import { Command } from "yuke:process";
import type { SessionRow } from "yuke:protocol";
import { Transcript } from "yuke:transcript";
import { Picker, stack, TextView } from "yuke:tui";
import { command, focusedEditor } from "../../lib.ts";
import type {} from "../../navigation.ts";
import { markdown } from "../../views.ts";

interface Result {
  readonly key: string;
  readonly kind: "session" | "chat" | "file" | "text";
  readonly session_id: string;
  readonly title: string;
  readonly detail: string;
  readonly path: string;
  readonly line: number;
  readonly message_id: string | number;
}

/** Search saved user and assistant text, paths, and workspace file contents. The index excludes tools and reasoning. */
export function apply(ctx: PluginContext): undefined {
  const tui = ctx.get("tui");
  if (tui === undefined) return;
  const sessions = ctx.get("sessions");
  const request = async <T>(value: unknown, cwd: string, signal: AbortSignal): Promise<T> => {
    const path = `${ctx.dataDir}/request-${Date.now()}-${Math.random().toString(36).slice(2)}.json`;
    await writeTextFile(path, JSON.stringify(value), { createNew: true, mode: 0o600, signal });
    try {
      const output = await new Command("python3", {
        args: [`${import.meta.dirname}/../../helpers/search-rust.py`, `${ctx.dataDir}/index.sqlite3`, path],
        cwd,
        signal,
      }).output();
      signal.throwIfAborted();
      if (!output.success) throw new Error(new TextDecoder().decode(output.stderr));
      return JSON.parse(new TextDecoder().decode(output.stdout)) as T;
    } finally {
      await remove(path, { force: true });
    }
  };
  command(
    ctx,
    tui,
    "search",
    "Search chats and workspace files",
    async (query) => {
      const editor = focusedEditor(tui);
      const pane = tui.panes.activePane;
      const cwd = pane === undefined ? tui.startup.folder : (ctx.get("chat").folder(pane.view) ?? tui.startup.folder);
      let scope: string | null = cwd;
      const sources = ["all", "chats", "files"] as const;
      let source = 0;
      let status = "Indexing chats…";
      let generation = 0;
      let previewGeneration = 0;
      let previewText = "Choose a result.";
      const preview = new TextView({ document: markdown("search-preview", previewText) });
      const show = async (item: Result): Promise<void> => {
        const navigation = ctx.get("personal-navigation");
        if (item.kind === "session" || item.kind === "chat") {
          await navigation.openSession(item.session_id);
          if (item.kind === "chat") {
            const active = tui.panes.activePane;
            const view = tui.widgets
              .list()
              .find(
                (mount) =>
                  mount.pane === active && mount.widget instanceof TextView && mount.widget.role === "transcript",
              )?.widget;
            if (view instanceof TextView) {
              const entry = view.document.items.find((entry) => entry.id === String(item.message_id));
              const section = entry?.sections[0];
              if (entry !== undefined && section !== undefined)
                view.ensureVisible({ item: entry.id, section: section.id, offset: 0 });
            }
          }
        } else await navigation.openFile(`${cwd}/${item.path}`, item.line || 1);
        dialog.close();
      };
      const failed = (error: unknown): void => {
        if (!dialog.signal.aborted) {
          status = String(error);
          tui.requestFrame();
        }
      };
      const loadPreview = async (item: Result | undefined): Promise<void> => {
        const serial = ++previewGeneration;
        if (item === undefined) return;
        const result = await request<{ text: string; note: string }>(
          { action: "preview", item, root: scope, query: picker.query },
          cwd,
          dialog.signal,
        );
        if (serial !== previewGeneration || dialog.signal.aborted) return;
        previewText = `${result.text}\n\n${result.note}`;
        preview.setDocument(markdown("search-preview", previewText));
      };
      const picker = new Picker<Result>({
        items: [],
        id: (item) => item.key,
        label: (item) => item.title,
        detail: (item) => `${item.kind} · ${item.detail}`,
        rank: (_query, items) => items.map((item) => ({ item })),
        onChoose: (item) => {
          void show(item).catch(failed);
        },
        onCancel: () => dialog.close(),
        onSelectionChange: (item) => {
          void loadPreview(item).catch(failed);
        },
      });
      const refresh = async (): Promise<void> => {
        const serial = ++generation;
        const result = await request<{ items: Result[]; note: string }>(
          { action: "search", query: picker.query, source: sources[source], root: scope },
          cwd,
          dialog.signal,
        );
        if (serial !== generation || dialog.signal.aborted) return;
        picker.setItems(result.items);
        status = `${result.items.length} results${result.note === "" ? "" : ` · ${result.note}`}`;
        tui.requestFrame();
      };
      const index = async (): Promise<void> => {
        const rows: SessionRow[] = [];
        let cursor: string | undefined;
        do {
          const page = await sessions.list({ limit: 100, ...(cursor === undefined ? {} : { cursor }) });
          rows.push(...page.sessions);
          cursor = page.nextCursor ?? undefined;
        } while (cursor !== undefined);
        const manifest = [];
        for (const row of rows) {
          const last = (await sessions.events(row.sessionId, { limit: 1 }))[0];
          manifest.push({
            id: row.sessionId,
            title: row.title ?? "(empty chat)",
            root: row.folder,
            signature: String(last?.seq ?? 0),
            updated: row.updatedAt,
          });
        }
        const dirty = await request<{ dirty: string[] }>({ action: "manifest", items: manifest }, cwd, dialog.signal);
        for (const id of dirty.dirty) {
          const transcript = new Transcript();
          let before: number | undefined;
          for (;;) {
            const page = await sessions.events(id, { limit: 200, ...(before === undefined ? {} : { before }) });
            transcript.insert(page);
            if (page.length < 200) break;
            before = page[0]?.seq;
          }
          const parts = transcript.entries.flatMap((entry) => {
            if (entry.kind === "text")
              return [{ session_id: id, message_id: entry.id, part_id: 0, role: "assistant", body: entry.text }];
            if (entry.kind !== "input" || entry.source.kind !== "user" || entry.inputKind !== "message") return [];
            return [
              {
                session_id: id,
                message_id: entry.id,
                part_id: 0,
                role: "user",
                body: entry.content.map((block) => (block.kind === "userText" ? block.text : "")).join("\n"),
              },
            ];
          });
          await request(
            { action: "index", session_id: id, signature: manifest.find((item) => item.id === id)?.signature, parts },
            cwd,
            dialog.signal,
          );
        }
        await refresh();
      };
      const dialog = tui.dialog({
        title: () => `Search · ${scope === null ? "all workspaces" : "workspace"} · ${sources[source]} · ${status}`,
        rows: Math.max(10, tui.size.height - 3),
        body: {
          ...stack("row", [
            { view: picker, size: (size) => Math.floor(size.width * 0.45) },
            { view: preview, size: "fill" },
          ]),
          initialFocus: picker.input,
        },
        keys: [
          {
            key: "tab",
            label: "scope",
            run: () => {
              scope = scope === null ? cwd : null;
              void refresh().catch(failed);
            },
          },
          {
            key: "ctrl+t",
            label: "source",
            run: () => {
              source = (source + 1) % sources.length;
              void refresh().catch(failed);
            },
          },
          {
            key: "ctrl+r",
            label: "reindex",
            run: () => {
              void index().catch(failed);
            },
          },
          {
            key: "ctrl+y",
            label: "insert",
            run: () => {
              const selected = picker.selectedItem;
              if (selected === undefined || editor === undefined) return;
              const text = selected.kind === "file" || selected.kind === "text" ? selected.path : previewText;
              const caret = editor.caret;
              dialog.close();
              editor.replace(caret, caret, text);
            },
          },
          { key: "ctrl+d", label: "preview down", run: () => preview.scroll.scrollBy(10) },
          { key: "ctrl+u", label: "preview up", run: () => preview.scroll.scrollBy(-10) },
        ],
      });
      const extension = picker.input.extend(dialog.signal);
      let cancelRefresh: (() => void) | undefined;
      extension.addChangeListener(() => {
        cancelRefresh?.();
        cancelRefresh = tui.addTimer(120, () => {
          void refresh().catch(failed);
        });
      });
      picker.query = query;
      await index();
    },
    "[query]",
  );
}
