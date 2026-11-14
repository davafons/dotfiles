import type { PluginContext } from "yuke:plugins";
import type { SessionRow } from "yuke:protocol";
import { Picker, TextView } from "yuke:tui";
import { command } from "../../lib.ts";
import type {} from "../../navigation.ts";
import { markdown } from "../../views.ts";

/** Browse sessions by workspace or across workspaces. Opening checks the native owner again. */
export function apply(ctx: PluginContext): undefined {
  const tui = ctx.get("tui");
  if (tui === undefined) return;
  const sessions = ctx.get("sessions");
  const open = async (): Promise<void> => {
    const pane = tui.panes.active;
    const cwd = pane === undefined ? tui.startup.cwd : (ctx.get("chat").folder(pane.view) ?? tui.startup.cwd);
    let all = false;
    let cursor: string | undefined;
    let busy = false;
    let rows: SessionRow[] = [];
    const picker = new Picker<SessionRow>({
      items: [],
      id: (row) => row.sessionId,
      label: (row) =>
        `${row.state === "running" ? "●" : row.state === "idle" ? "○" : " "} ${row.title?.replace(/\s+/g, " ") ?? "(empty chat)"}`,
      detail: (row) => `${row.model.provider}/${row.model.model} · ${row.cwd}`,
      onChoose: (row) => {
        void ctx
          .get("personal-navigation")
          .openSession(row.sessionId)
          .then(
            () => dialog.close(),
            (error: unknown) => ctx.notify("error", String(error)),
          );
      },
      onCancel: () => dialog.close(),
    });
    const load = async (more = false): Promise<void> => {
      if (busy) return;
      busy = true;
      try {
        const page = await sessions.list({
          limit: 100,
          ...(all ? {} : { cwd }),
          ...(more && cursor !== undefined ? { cursor } : {}),
        });
        if (dialog.signal.aborted) return;
        rows = more ? [...rows, ...page.sessions] : page.sessions;
        cursor = page.nextCursor ?? undefined;
        picker.setItems(rows);
        tui.requestFrame();
      } finally {
        busy = false;
      }
    };
    const failed = (error: unknown): void => ctx.notify("error", String(error));
    const dialog = tui.dialog({
      title: () => `Sessions · ${all ? "all workspaces" : cwd} · ${rows.length}`,
      body: picker,
      rows: 22,
      keys: [
        {
          key: "tab",
          label: "scope",
          when: () => !busy,
          run: () => {
            all = !all;
            void load().catch(failed);
          },
        },
        {
          key: "ctrl+r",
          label: "refresh",
          when: () => !busy,
          run: () => {
            void load().catch(failed);
          },
        },
        {
          key: "ctrl+n",
          label: "more",
          when: () => !busy && cursor !== undefined,
          run: () => {
            void load(true).catch(failed);
          },
        },
        {
          key: "ctrl+d",
          label: "delete",
          when: () => !busy && picker.selected !== undefined,
          run: () => {
            const selected = picker.selected;
            if (selected === undefined) return;
            const confirm = tui.dialog({
              title: () => "Delete this session and its children?",
              body: new TextView({
                document: markdown("delete-session", selected.title ?? selected.sessionId),
              }),
              rows: 5,
              signal: dialog.signal,
              keys: [
                {
                  key: "enter",
                  label: "delete",
                  run: () => {
                    confirm.close();
                    void sessions.remove(selected.sessionId).then(() => load(), failed);
                  },
                },
              ],
            });
          },
        },
      ],
    });
    await load();
  };
  command(ctx, tui, "sessions", "Browse saved conversations", open);
  command(ctx, tui, "resume", "Browse saved conversations", open);
}
