import { composerRows } from "yuke:chat";
import type { PluginContext } from "yuke:plugins";
import { Picker, stack, TextEditor, TextView, type Tui } from "yuke:tui";
import { command, currentSession } from "../../lib.ts";
import { markdown } from "../../views.ts";
import { owners } from "./presence.ts";

type Status = "now" | "later" | "blocked" | "review" | "done";
interface Task {
  id: string;
  title: string;
  status: Status;
  notes: string;
  github_url: string;
  version: number;
  owner_session: string;
  owner_root: string;
}
interface Message {
  session: string;
  body: string;
}
interface Github {
  number: number;
  title: string;
  url: string;
  state: string;
  body?: string;
  kind: "issues" | "pulls";
  ci?: string;
  review?: string;
}
type Item = { key: string; task: Task; github?: never } | { key: string; github: Github; task?: never };

/** Task editing stays in the terminal. GitHub reads never change remote items. */
export function install(
  ctx: PluginContext,
  tui: Tui,
  request: <T>(value: unknown, cwd: string, signal: AbortSignal) => Promise<T>,
  github: <T>(value: unknown, cwd: string, signal: AbortSignal) => Promise<T>,
): void {
  const chat = ctx.get("chat");
  const noRows: never[] = [];
  const mutations = new Map<string, { eventNumber: number; blockIndex: number }>();
  const assigned = new Map<string, readonly { text: string }[]>();
  const refreshAssignment = async (): Promise<void> => {
    const pane = tui.panes.active;
    if (pane === undefined) return;
    const id = chat.session(pane.view),
      cwd = chat.folder(pane.view);
    if (id === undefined || cwd === undefined) return;
    const result = await request<{ tasks: Task[] }>({ action: "assigned", session: id }, cwd, ctx.signal);
    assigned.set(
      id,
      result.tasks.map((task) => ({ text: `work  ${task.title} · ${task.status} · /work` })),
    );
    tui.requestFrame();
  };
  const stopRows = chat.addComposerView("above", (_mount, pane) =>
    composerRows(() => (pane.session === undefined ? noRows : (assigned.get(pane.session) ?? noRows))),
  );
  ctx.signal.addEventListener("abort", stopRows, { once: true });
  const stopChange = chat.addChangeListener(() => {
    void refreshAssignment().catch((error: unknown) => ctx.notify("warn", String(error)));
  });
  ctx.signal.addEventListener("abort", stopChange, { once: true });
  ctx.addListener("session.update", (event) => {
    const update = event.update;
    if (update.sessionUpdate === "toolStarted" && update.call.name === "project_work")
      mutations.set(event.sessionId, update.position);
    else if (update.sessionUpdate === "toolFinished") {
      const position = mutations.get(event.sessionId);
      if (position?.eventNumber !== update.position.eventNumber || position.blockIndex !== update.position.blockIndex)
        return;
      mutations.delete(event.sessionId);
      void refreshAssignment().catch((error: unknown) => ctx.notify("warn", String(error)));
    }
  });
  const open = async (): Promise<void> => {
    const pane = tui.panes.active;
    const cwd = pane === undefined ? tui.startup.cwd : (chat.folder(pane.view) ?? tui.startup.cwd);
    const session = currentSession(ctx, tui) ?? "";
    let tab: "tasks" | "issues" | "pulls" = "tasks";
    let offset = 0,
      total = 0;
    let cursor: string | undefined;
    let includeDone = false,
      busy = false,
      refreshQueued = false;
    let generation = 0;
    let current: Task | undefined;
    const preview = new TextView({ document: markdown("task", "Select a task to read its notes and messages.") });
    const failed = (error: unknown): void => {
      if (!dialog.signal.aborted && !ctx.signal.aborted) ctx.notify("error", String(error));
    };
    const select = async (row: Item | undefined): Promise<void> => {
      const version = ++generation;
      current = undefined;
      if (row === undefined) {
        preview.setDocument(markdown("task", "No matching work."));
        return;
      }
      if (row.task !== undefined) {
        const detail = await request<{ task: Task; messages: Message[] }>(
          { action: "get", id: row.task.id },
          cwd,
          dialog.signal,
        );
        if (version !== generation || dialog.signal.aborted) return;
        current = detail.task;
        preview.setDocument(
          markdown(
            "task",
            `# ${detail.task.title}\n\n${detail.task.status} · ${detail.task.id} · v${detail.task.version}\n\nAssigned: ${detail.task.owner_session || "unassigned"}\n\n${detail.task.github_url}\n\n${detail.task.notes}\n\n## Messages\n${detail.messages.map((message) => `**${message.session}**\n${message.body}`).join("\n\n")}`,
          ),
        );
      } else {
        const detail = await github<{ item: Github }>(
          { action: "get", kind: row.github.kind, url: row.github.url },
          cwd,
          dialog.signal,
        );
        if (version !== generation || dialog.signal.aborted) return;
        preview.setDocument(
          markdown(
            "task",
            `# #${detail.item.number} ${detail.item.title}\n\n${detail.item.state} · ${detail.item.ci ?? ""} · ${detail.item.review ?? ""}\n\n${detail.item.url}\n\n${detail.item.body ?? ""}`,
          ),
        );
      }
      tui.requestFrame();
    };
    const picker = new Picker<Item>({
      items: [],
      id: (row) => row.key,
      label: (row) =>
        row.task === undefined ? `#${row.github.number} ${row.github.title}` : `[${row.task.status}] ${row.task.title}`,
      detail: (row) =>
        row.task === undefined
          ? `${row.github.state} · ${row.github.ci ?? ""}`
          : row.task.owner_session
            ? `assigned ${row.task.owner_session}`
            : "unassigned",
      onSelectionChange: (row) => {
        void select(row).catch(failed);
      },
      onChoose: () => {
        tui.focus(preview);
      },
      onCancel: () => dialog.close(),
    });
    const load = async (): Promise<void> => {
      if (busy) {
        refreshQueued = true;
        return;
      }
      busy = true;
      try {
        if (tab === "tasks") {
          let result = await request<{ tasks: Task[]; total: number }>(
            { action: "list", offset, include_done: includeDone },
            cwd,
            dialog.signal,
          );
          if (result.tasks.some((task) => task.owner_session !== "")) {
            const presence = await request<{ released: string[] }>(
              {
                action: "presence",
                ...(await owners(
                  ctx.get("sessions"),
                  result.tasks.map((task) => task.owner_session),
                  dialog.signal,
                )),
              },
              cwd,
              dialog.signal,
            );
            if (presence.released.length > 0)
              result = await request({ action: "list", offset, include_done: includeDone }, cwd, dialog.signal);
          }
          total = result.total;
          if (!dialog.signal.aborted) picker.setItems(result.tasks.map((task) => ({ key: task.id, task })));
        } else {
          const result = await github<{ items: Github[]; total: number; next_cursor: string | null }>(
            { action: "list", kind: tab, ...(cursor === undefined ? {} : { cursor }) },
            cwd,
            dialog.signal,
          );
          total = result.total;
          cursor = result.next_cursor ?? undefined;
          if (!dialog.signal.aborted) picker.setItems(result.items.map((github) => ({ key: github.url, github })));
        }
        await refreshAssignment();
      } finally {
        busy = false;
        tui.requestFrame();
        if (refreshQueued && !dialog.signal.aborted) {
          refreshQueued = false;
          void load().catch(failed);
        }
      }
    };
    const mutate = async (value: unknown): Promise<void> => {
      await request(value, cwd, dialog.signal);
      await load();
    };
    const form = (task?: Task, linked?: Github): void => {
      const title = new TextEditor({
        placeholder: "Task title",
        state: { text: task?.title ?? linked?.title ?? "", spans: [], selection: { anchor: 0, head: 0 } },
      });
      const notes = new TextEditor({
        placeholder: "Scope, decisions, acceptance, verification…",
        state: { text: task?.notes ?? "", spans: [], selection: { anchor: 0, head: 0 } },
      });
      const link = new TextEditor({
        placeholder: "Optional github.com issue or PR URL",
        state: { text: task?.github_url ?? linked?.url ?? "", spans: [], selection: { anchor: 0, head: 0 } },
      });
      let status: Status = task?.status ?? "later",
        saving = false;
      const edit = tui.dialog({
        title: () => `${task === undefined ? "New task" : "Edit task"} · ${status}`,
        signal: dialog.signal,
        body: {
          ...stack("column", [
            { view: title, size: 2 },
            { view: notes, size: "fill" },
            { view: link, size: 2 },
          ]),
          initialFocus: title,
        },
        rows: Math.max(12, tui.size.height - 4),
        keys: [
          {
            key: "tab",
            label: "next field",
            run: () => {
              tui.focus(tui.focused === title ? notes : tui.focused === notes ? link : title);
            },
          },
          {
            key: "ctrl+t",
            label: "status",
            when: () => !saving,
            run: () => {
              void tui
                .select({
                  title: "Task status",
                  items: (["now", "later", "blocked", "review", "done"] as const).map((value) => ({ value })),
                  label: (row) => row.value,
                  signal: edit.signal,
                })
                .then((row) => {
                  if (row !== undefined) {
                    status = row.value;
                    tui.requestFrame();
                  }
                })
                .catch(failed);
            },
          },
          {
            key: "ctrl+s",
            label: "save",
            when: () => !saving,
            run: () => {
              saving = true;
              void mutate({
                action: "task",
                title: title.state.text,
                notes: notes.state.text,
                status,
                github_url: link.state.text,
                session,
                ...(task === undefined ? {} : { id: task.id, version: task.version }),
              })
                .then(() => edit.close())
                .catch(failed)
                .finally(() => {
                  saving = false;
                });
            },
          },
        ],
      });
      tui.focus(title);
    };
    const message = (): void => {
      const task = current;
      if (task === undefined) return;
      const editor = new TextEditor({ placeholder: "Task coordination message…" });
      const edit = tui.dialog({
        title: () => "Post task message · no notification or model turn",
        body: editor,
        rows: 10,
        signal: dialog.signal,
        keys: [
          {
            key: "ctrl+s",
            label: "post",
            run: () => {
              void mutate({ action: "message", id: task.id, body: editor.state.text, session })
                .then(() => edit.close())
                .catch(failed);
            },
          },
        ],
      });
    };
    const dialog = tui.dialog({
      title: () => `Project work · ${tab} · ${busy ? "loading…" : total} · ${cwd}`,
      body: {
        ...stack("row", [
          { view: picker, size: "fill" },
          { view: preview, size: "fill" },
        ]),
        initialFocus: picker.input,
      },
      rows: Math.max(12, tui.size.height - 2),
      keys: [
        {
          key: "tab",
          label: "tasks/issues/PRs",
          when: () => !busy,
          run: () => {
            tab = tab === "tasks" ? "issues" : tab === "issues" ? "pulls" : "tasks";
            offset = 0;
            cursor = undefined;
            void load().catch(failed);
            tui.focus(picker);
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
          label: "next page",
          when: () => !busy,
          run: () => {
            if (tab === "tasks") {
              if (offset + 10 >= total) return;
              offset += 10;
            } else if (cursor === undefined) return;
            void load().catch(failed);
          },
        },
        {
          key: "ctrl+p",
          label: "first page",
          when: () => !busy,
          run: () => {
            offset = 0;
            cursor = undefined;
            void load().catch(failed);
          },
        },
        {
          key: "ctrl+d",
          label: "include done",
          when: () => tab === "tasks" && !busy,
          run: () => {
            includeDone = !includeDone;
            offset = 0;
            void load().catch(failed);
          },
        },
        { key: "alt+n", label: "new task", run: () => form(undefined, picker.selected?.github) },
        { key: "alt+e", label: "edit", when: () => current !== undefined, run: () => form(current) },
        { key: "alt+m", label: "message", when: () => current !== undefined, run: message },
        {
          key: "ctrl+g",
          label: "claim/release",
          when: () => current !== undefined && session !== "",
          run: () => {
            if (current !== undefined)
              void mutate({
                action: current.owner_session === session ? "release" : "claim",
                id: current.id,
                version: current.version,
                session,
              }).catch(failed);
          },
        },
        {
          key: "alt+u",
          label: "unassign owner",
          when: () => !!current?.owner_session,
          run: () => {
            const task = current;
            if (task === undefined) return;
            const confirm = tui.dialog({
              title: () => "Unassign this session?",
              body: new TextView({
                document: markdown(
                  "unassign",
                  `${task.title}\n\nCurrent owner: ${task.owner_session}\n\nClear only an abandoned or coordinated assignment. Scope and status stay the same.`,
                ),
              }),
              rows: 8,
              signal: dialog.signal,
              keys: [
                {
                  key: "enter",
                  label: "unassign",
                  run: () => {
                    confirm.close();
                    void mutate({ action: "release", id: task.id, version: task.version, force: true, session }).catch(
                      failed,
                    );
                  },
                },
              ],
            });
          },
        },
        {
          key: "ctrl+o",
          label: "assigned session",
          when: () => !!current?.owner_session,
          run: () => {
            if (current !== undefined)
              void ctx
                .get("personal-navigation")
                .openSession(current.owner_session)
                .then(() => dialog.close())
                .catch(failed);
          },
        },
        {
          key: "ctrl+f",
          label: "focus list/notes",
          run: () => {
            tui.focus(tui.focused === preview ? picker : preview);
          },
        },
      ],
    });
    await load();
  };
  command(ctx, tui, "work", "Open project tasks and GitHub work", open);
}
