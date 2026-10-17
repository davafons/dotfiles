//! Shared project tasks and read-only GitHub work. No storage or model calls run during draw.
import { client, env, exec, fs, events } from "yuke";
import { currentEntry, currentPane, currentSession, showSession } from "yuke:session";
import { ChatView } from "yuke:chat";
import { ui, Window } from "yuke:ui";
import { WorkDashboard, SessionTaskIndicator } from "./project-work-view.js";
import { readActivity } from "./activity.js";
import { readGitHub } from "./project-work-github.js";
import { focusHerdrSession, herdrSessionPanes } from "../herdr/index.js";
/** @import { CancellationSignal } from "yuke" */
/** @import { Task, BoardSnapshot } from "./project-work-view.js" */
/** @typedef {{ label: string, kind: string, id?: string }} MenuItem */

const statuses = ["now", "later", "blocked", "review", "done"];
const properties = {
  action: { type: "string", enum: ["list", "get", "task", "notes", "claim", "release", "message", "progress"] },
  id: { type: "string", maxLength: 100, description: "Task ID for get or task update. Omit to create a task." },
  version: { type: "integer", minimum: 0, description: "Version from the latest read or mutation receipt. Required for updates and progress." },
  title: { type: "string", maxLength: 200 },
  status: { type: "string", enum: statuses },
  notes: { type: "string", maxLength: 4000, description: "Markdown task notes. Use short paragraphs, headings and bullet points. Keep coordination history in task messages." },
  body: { type: "string", maxLength: 2000, description: "Markdown task message for action message. Requires id. Appends a session-attributed coordination message without replacing notes; does not notify or start another session." },
  github_url: { type: "string", maxLength: 500, description: "Optional github.com issue or PR URL. Empty clears the link; omit to retain it on an update. Internal status never updates GitHub." },
  offset: { type: "integer", minimum: 0, description: "Task page offset. Each list returns at most 10 tasks." },
  include_done: { type: "boolean", description: "Include completed tasks in list. Defaults to false." },
};

/** @param {string} value */
function quote(value) { return "'" + value.replaceAll("'", "'\\''") + "'"; }

/** Register the migrated project-work operations. The plugin owns registrations; host failures throw. @param {import("yuke").Context} parent */
export default function(parent) {

    const home = env.get("HOME") || ".";
    const app = env.get("YUKE_APPNAME") || "yuke";
    const config = (env.get("XDG_CONFIG_HOME") || home + "/.config") + "/" + app;
    const githubHelper = config + "/plugins/project-work-github.py";
    const database = (env.get("XDG_STATE_HOME") || home + "/.local/state") + "/" + app + "/work/work.sqlite3";
    let tail = Promise.resolve();
    let refreshAssignments = () => {};

    /** @param {Record<string, unknown>} args @param {CancellationSignal} [signal] */
    function store(args, signal = parent.signal) {
      const operation = tail.then(async () => {
        if (!parent.alive || signal.aborted) throw new Error("Work operation canceled.");
        let output = "";
        const result = await exec(["python3", config + "/plugins/project-work-store.py", database, JSON.stringify({ ...args, api_version: 2 })].map(quote).join(" "), {
          signal, timeoutMs: 15000, mergeStderr: true,
          onOutput: (chunk) => { output += chunk; },
        });
        if (result.code !== 0) throw new Error((output || result.stdout || "Work storage failed.").trim());
        const reply = JSON.parse(output);
        if (["task", "claim", "release", "progress"].includes(String(args.action)) || (args.action === "presence" && reply.released?.length)) refreshAssignments();
        return reply;
      });
      tail = operation.then(() => {}, () => {});
      return operation;
    }
    parent.own(async () => { await tail; });

    parent.hook("prompt.build", (payload) => ({ replace: { sections: [...payload.sections, {
      key: "project-work",
      text: "Use project_work list when starting substantial work or resuming a project. Tasks are shared across linked checkouts. Read list/get when starting or resuming, or after a version conflict. Reuse the id/version returned by successful reads or mutations. For routine progress, prefer progress with a short body and optional status; it preserves scope notes. Rewrite scope notes only when scope, decisions, or acceptance changes. Do not reread a task solely to obtain the version you just received. Assign yourself a task with claim before working on it. Saving a task as now also claims it when unowned. A task is assigned directly to one session. A session can have only one assigned task across all projects. Complete or release the current task before claiming another. Child agents use their own session assignments. Work reads release claims only when a native tree lock proves the owner closed; idle, blocked and unknown presence retain claims. Never infer assignment from a creator chat or the now status. If another session is assigned to the task, post a message to coordinate or choose another task. Messages are read with get or UI refresh, not pushed to sessions. Release your claim when you stop working on the task; done releases it. Update notes in readable Markdown with short paragraphs and bullets. Use notes for notes-only edits; it preserves status and ownership. Keep task notes current with scope, decisions, and verification. Record failed and unrun checks. Do not mark a task done just because a run ended. The user reads /work. Reading records or preparing a brief does not authorize delegation, sending external messages, pushing, merging, or deployment. GitHub is the outer loop; read github_work for linked issues/PRs and keep internal task status separate. github_work is read-only.",
    }] } }));
    parent.tools.define({
      name: "project_work",
      description: "Read and save shared project tasks. Reads release claims only after native ownership-lock proof that the owner closed; idle and unknown owners are retained. list returns paged tasks. owner_session/owner_root are the assigned session and checkout, not another ownership layer. Each session can have only one assigned task; complete or release it before claiming another. get requires id and includes latest 20 task messages. notes updates only Markdown notes with fresh id/version, without claiming a task. task requires title/status/Markdown notes; updates require fresh id/version and refuse another assigned session. Saving now claims an unowned task. claim/release require id/version; claim moves to now, and only the assigned session may release. message requires id/body and appends coordination text attributed to this session, without notification or starting agents. done releases ownership. progress requires id/version/body and the current owner; it atomically appends progress and optionally changes status without replacing notes. A done status releases ownership. Replaying a tool call returns the original receipt without repeating effects. No GitHub writes or automatic completion.",
      parameters: { type: "object", additionalProperties: false, properties, required: ["action"] },
      async execute(args, signal, toolCtx) {
        if (!args || typeof args !== "object" || Array.isArray(args)) throw new Error("Work arguments must be an object.");
        const value = /** @type {Record<string, unknown>} */ (args);
        if (Object.keys(value).some((key) => !(key in properties)) || !properties.action.enum.includes(/** @type {string} */ (value.action))) {
          throw new Error("Unknown work action or field.");
        }
        const request = { ...value, root: toolCtx.workspaceRoot, session: toolCtx.sessionId,
          site: `${toolCtx.sessionId}:${toolCtx.messageId}:${toolCtx.partId}` };
        let reply = await store(request, signal);
        if (value.action === "list" || value.action === "get") {
          const owners = value.action === "get" ? [reply.task.owner_session].filter(Boolean) : Object.keys(reply.owner_counts || {});
          let released = false;
          if (owners.length) await readActivity(owners, signal, async (roots, openSessions) => {
            const presence = await store({ action: "presence", root: toolCtx.workspaceRoot, session: toolCtx.sessionId, roots, open_sessions: openSessions }, signal);
            released = presence.released.length > 0;
            return presence;
          });
          if (released) reply = await store(request, signal);
        }
        return JSON.stringify(reply);
      },
    });

    const githubProperties = {
      action: { type: "string", enum: ["list", "get"] },
      kind: { type: "string", enum: ["issues", "pulls"], description: "Defaults to issues." },
      state: { type: "string", enum: ["open", "closed", "all"], description: "List filter; closed pulls includes merged PRs." },
      cursor: { type: "string", maxLength: 1000, description: "next_cursor from list. Each page has at most 20 records." },
      number: { type: "integer", minimum: 1, description: "Required for get." },
    };
    parent.tools.define({
      name: "github_work",
      description: "Read the calling project's GitHub issues and PRs through gh. list returns a cursor page with review and CI rollups for PRs. get returns body, up to 20 CI checks, and up to 50 linked internal tasks. No GitHub writes, automatic task imports, or status synchronization. Requires gh authentication.",
      parameters: { type: "object", additionalProperties: false, properties: githubProperties, required: ["action"] },
      async execute(args, signal, toolCtx) {
        if (!args || typeof args !== "object" || Array.isArray(args)) throw new Error("GitHub arguments must be an object.");
        const value = /** @type {Record<string, unknown>} */ (args);
        if (Object.keys(value).some((key) => !(key in githubProperties)) || !githubProperties.action.enum.includes(/** @type {string} */ (value.action))) throw new Error("Unknown GitHub read action or field.");
        const reply = await readGitHub(githubHelper, toolCtx.workspaceRoot, value, signal);
        if (value.action === "get") {
          const linked = await store({ action: "linked", root: toolCtx.workspaceRoot, session: toolCtx.sessionId, github_url: reply.item.url }, signal);
          reply.linked_tasks = linked.tasks;
          reply.linked_task_count = linked.total;
        }
        return JSON.stringify(reply);
      },
    });

    {
const tuiBorrow = parent.get("tui");
if (tuiBorrow) {
const c = { ctx: parent, tui: tuiBorrow };

      c.tui.style.set({
        WorkText: { link: "UIPanel", fg: "fg" },
        WorkCard: { link: "UIPanel", bg: "surface" },
        WorkDim: { link: "UIPanel", fg: "fg", dim: true },
        WorkTitle: { link: "UIPanel", fg: "accent", bold: true },
        WorkRule: { link: "UIPanel", fg: "accent" },
        WorkShortcut: { link: "UIPanel", fg: "accent" },
        WorkDanger: { link: "UIPanel", fg: "danger", bold: true },
        WorkActiveTab: { link: "UIPanel", fg: "bg", bg: "accent", bold: true },
      });
      const indicator = new SessionTaskIndicator(async session => {
        const item = await client.sessionGet(session);
        return store({action:"assigned", root:item.session.root, session});
      }, () => { if (c.ctx.alive) c.tui.root.invalidate(); });
      function visibleSessions() {
        const ids = [];
        for (const leaf of c.tui.root.root_node?.leaves() || []) {
          if (leaf.shape?.type !== "leaf") continue;
          const pane = leaf.shape.view;
          if (pane instanceof ChatView && pane.session.sessionId) ids.push(pane.session.sessionId);
        }
        return ids;
      }
      refreshAssignments = () => { if (c.ctx.alive) void indicator.refresh(visibleSessions()); };
      c.ctx.on("session.current.changed", refreshAssignments);
      c.ctx.on("pane.focused", refreshAssignments);
      c.ctx.on("ui.started", refreshAssignments);
      const assignmentPoll = setInterval(refreshAssignments, 3000);
      c.ctx.own(() => { clearInterval(assignmentPoll); indicator.close(); refreshAssignments = () => {}; });
      c.ctx.advise(events, "bail", "around", (next, name, ...args) => {
        const rows = next(name, ...args);
        if (name !== "chat.strip") return rows;
        const view = /** @type {import("yuke:chat").ChatView} */ (args[0]);
        return [...(Array.isArray(rows) ? rows : []), indicator.row(view.session.sessionId, view.rect.w)];
      });
      let releaseColors = () => {};
      const applyColors = () => {
        releaseColors();
        const palette = c.tui.style.palette;
        const dark = c.tui.background === "dark";
        const fallback = c.tui.colors === "truecolor"
          ? dark ? ["#4695f7", "#41c7b9", "#dbb32d", "#b7a2e8", "#75b938"] : ["#006599", "#006f66", "#765c00", "#724b9e", "#3b6b14"]
          : dark ? [75, 80, 179, 183, 113] : [24, 23, 58, 60, 22];
        const names = ["Now", "Later", "Blocked", "Review", "Done"];
        const colors = [palette.accent, palette.cyan, palette.warn, palette.violet, palette.green];
        /** @type {Parameters<typeof c.tui.style.set>[0]} */
        const groups = {};
        for (let i = 0; i < names.length; i++) {
          const color = colors[i] ?? fallback[i];
          groups["Work" + names[i]] = { link: "UIPanel", fg: color, bold: true };
          groups["WorkSelected" + names[i]] = { link: "UIPanel", fg: "bg", bg: color, bold: true };
        }
        releaseColors = c.tui.style.set(groups);
      };
      applyColors();
      c.ctx.on("background.changed", applyColors);

      c.ctx.own(() => releaseColors());
      let busy = false;
      /** @type {ReturnType<typeof currentPane>} */
      let ownerPane = null;
      /** @type {string | null} */
      let ownerSession = null;

      function ensurePane() {
        if (!c.ctx.alive || !ownerPane || currentPane() !== ownerPane || ownerPane.session.sessionId !== ownerSession) {
          throw new Error("The pane changed while reading work. Open /work again.");
        }
      }

      /** @returns {Promise<{ root: string, session: string }>} */
      async function location() {
        const session = currentSession()?.sessionId || "";
        const entry = currentEntry();
        const root = session ? entry?.session.root || (await client.sessionGet(session)).session.root : (await fs.stat("."))?.path;
        if (!root) throw new Error("This pane has no project directory.");
        return { root, session };
      }

      /** @param {string} title @param {MenuItem[]} items @param {string} [body] @returns {Promise<MenuItem | undefined>} */
      function pick(title, items, body = "") {
        ensurePane();
        return new Promise((resolve) => {
          let close = () => {};
          const { win } = ui.pick({
            title, items, body, width: (width) => Math.min(width, 100), height: (height) => Math.max(1, height - 4),
            filter: false, closeOnAccept: false, format: (item) => item.label,
            footer: "Enter: choose · Esc: close · PageUp/PageDown: scroll details",
            onAccept: (item) => { resolve(item); close(); },
          });
          close = c.tui.overlay(win, () => resolve(undefined));
        });
      }

      /** @param {string} session */
      async function resume(session) {
        if (!session) throw new Error("This item has no saved session. Prepare a task brief instead.");
        const panes = await herdrSessionPanes(c.ctx.signal);
        if (!c.ctx.alive) return;
        ensurePane();
        if (panes.has(session) && panes.get(session) !== env.get("HERDR_PANE_ID")) {
          await focusHerdrSession(session, c.ctx.signal);
          return;
        }
        const pane = currentPane();
        if (!pane) throw new Error("No chat pane is available.");
        if (pane.session.sessionId !== session && pane.composer?.input.text) {
          throw new Error("Your composer has an unsent draft. Save or clear it before resuming another session.");
        }
        await client.sessionGet(session);
        if (!c.ctx.alive) return;
        ensurePane();
        showSession(pane, session);
      }

      /** @param {{root: string, session: string}} source @param {string} [title] */
      async function addTask(source, title) {
        const name = title || await c.ctx.interaction.input("Save a task for later", "Task title");
        if (name == null || !c.ctx.alive) return;
        ensurePane();
        await store({ action: "task", ...source, title: name, status: "later", notes: "" }, c.ctx.signal);
        if (c.ctx.alive) c.ctx.interaction.notify("Task saved for later.");
      }

      /** @param {Task} task @param {Pick<BoardSnapshot, "root">} snapshot */
      function prepare(task, snapshot) {
        ensurePane();
        const pane = currentPane();
        const input = pane?.composer?.input;
        if (!input) throw new Error("No composer is available.");
        if (input.text) throw new Error("Your composer has an unsent draft. Nothing changed.");
        input.setText([
          `Continue project task ${task.id}: ${task.title}`,
          "Read project_work before changing its records. Verify the checkout and current state before making changes.",
          "Target checkout: " + snapshot.root,
          ...(task.notes ? ["Task notes: " + task.notes] : []),
          ...(task.github_url ? ["GitHub outer loop: " + task.github_url + "\nRead github_work before continuing. Internal completion does not change GitHub status."] : []),
        ].join("\n\n"));
      }

      async function openWork() {
        const source = await location();
        if (!c.ctx.alive) return;
        ensurePane();
        /** @type {import("yuke").CancellationSignal} */
        let githubSignal = c.ctx.signal;
        /** @type {Set<ReturnType<typeof readGitHub>>} */
        const githubReads = new Set();
        /** @type {Set<ReturnType<typeof readActivity>>} */
        const activityReads = new Set();
        const githubOwner = c.ctx.resources("project-work-github-dialog");
        githubSignal = githubOwner.signal;
        githubOwner.own(() => { view.close(); return Promise.allSettled([...githubReads, ...activityReads]).then(() => {}); });
        /** @param {Record<string, unknown>} args */
        function fetchGitHub(args) {
          const operation = readGitHub(githubHelper, source.root, args, githubSignal);
          githubReads.add(operation);
          return operation.finally(() => githubReads.delete(operation));
        }
        const view = new WorkDashboard(c, {
          activityRead(ids) {
            const operation = readActivity(ids, githubSignal, async (roots, openSessions) => store({ action: "presence", ...source, roots, open_sessions: openSessions }, githubSignal));
            activityReads.add(operation);
            return operation.finally(() => activityReads.delete(operation));
          },
          githubRead: async (args) => fetchGitHub(args),
          githubDetail: async (args) => {
            const reply = await fetchGitHub(args);
            if (githubSignal.aborted) throw new Error("GitHub read canceled.");
            const linked = await store({ action: "linked", ...source, github_url: reply.item.url }, githubSignal);
            return { ...reply, linked_tasks: linked.tasks, linked_task_count: linked.total };
          },
          read: async (offsets, query, done) => store({ action: "board", ...source, offsets, query, include_done: done }, c.ctx.signal),
          detail: async (id) => store({ action: "get", ...source, id }, c.ctx.signal),
          async action(name, task) {
            ensurePane();
            if (name === "github_add" || name === "github_task") {
              const item = view.selectedGitHubItem();
              if (!item) return;
              if (name === "github_task" && !view.githubDetail) throw new Error("GitHub details are still loading. Try Enter again.");
              if (name === "github_task" && view.githubDetail?.linked_tasks.length) {
                const selected = await pick("Internal steps for #" + item.number, [
                  { label: "Add an internal step", kind: "add" },
                  ...view.githubDetail.linked_tasks.map((linked) => ({ label: linked.status + " · " + linked.title, kind: "task", id: linked.id })),
                ]);
                if (!selected || !c.ctx.alive) return;
                if (selected.id) {
                  const detail = await store({ action: "get", ...source, id: selected.id }, c.ctx.signal);
                  if (c.ctx.alive) view.inspect(detail.task);
                  return;
                }
              }
              const defaultTitle = Array.from(item.title).slice(0, 200).join("");
              const title = await c.ctx.interaction.input("Internal step for GitHub #" + item.number, "Blank uses: " + defaultTitle);
              if (title == null || !c.ctx.alive) return;
              ensurePane();
              await store({ action: "task", ...source, title: title.trim() || defaultTitle, status: "later", notes: "", github_url: item.url }, c.ctx.signal);
              c.ctx.interaction.notify("Linked internal task saved. GitHub did not change.");
            } else if (name === "add") await addTask(source);
            else if (task) {
              const detail = /** @type {{task: Task}} */ (await store({ action: "get", ...source, id: task.id }, c.ctx.signal));
              if (!c.ctx.alive) return;
              ensurePane();
              if (name === "prepare") { prepare(detail.task, { root: view.data?.root || source.root }); return "close"; }
              if (name === "session") {
                const session = detail.task.owner_session;
                if (!session) throw new Error("This task is not assigned to a session. Assign it before opening its chat.");
                await resume(session); return "close";
              }
              if (name === "claim" || name === "release") {
                if (!source.session) throw new Error("Start a saved conversation before assigning a task.");
                let force = false;
                if (name === "release" && detail.task.owner_session && detail.task.owner_session !== source.session) {
                  force = Boolean(await c.ctx.interaction.confirm("Unassign " + detail.task.owner_session + "? This does not stop that session. Coordinate before reassigning."));
                  if (!force || !c.ctx.alive) return;
                }
                ensurePane();
                await store({ action: name, ...source, id: task.id, version: detail.task.version, ...(force ? { force: true } : {}) }, c.ctx.signal);
              } else if (name === "message" || name === "notes") {
                const value = await c.ctx.interaction.input(name === "message" ? "Message to task participants (read on refresh)" : "Task notes (Markdown; blank clears)", name === "notes" ? detail.task.notes : "");
                if (value == null || !c.ctx.alive) return;
                ensurePane();
                if (name === "message") await store({ action: "message", ...source, id: task.id, body: value }, c.ctx.signal);
                else await store({ action: "notes", ...source, id: task.id, version: detail.task.version, notes: value }, c.ctx.signal);
              }
              if (name === "status") {
                const status = await c.ctx.interaction.select("Task status", statuses);
                if (status == null || !c.ctx.alive) return;
                ensurePane();
                await store({ action: "task", ...source, id: detail.task.id, version: detail.task.version,
                  title: detail.task.title, notes: detail.task.notes, status }, c.ctx.signal);
              }
            }
          },
        });
        const win = new Window({ border: "none", width: (max) => max, height: (max) => max,
          outsidePress: "ignore", content: view, footer: () => view.footer });
        const pollActivity = setInterval(() => { void view.refreshActivity(); }, 1000);
        const pollBoard = setInterval(() => { void view.refresh(true); }, 3000);
        const animateActivity = setInterval(() => { view.animate(); }, 200);
        githubOwner.own(() => { clearInterval(pollActivity); clearInterval(pollBoard); clearInterval(animateActivity); });
        try {
          await new Promise((resolve) => {
            view.close = c.tui.overlay(win, () => { view.closed = true; resolve(undefined); });
            void view.refresh();
          });
        } finally { await githubOwner.dispose(); }
      }

      /** @param {() => Promise<void>} action */
      function run(action) {
        if (busy) return;
        busy = true;
        ownerPane = currentPane();
        ownerSession = ownerPane?.session.sessionId || null;
        void action().catch((error) => { if (c.ctx.alive) c.ctx.interaction.notify(String(error), "error"); }).finally(() => { busy = false; });
      }
      c.tui.command.add("work", { desc: "organize tasks and review GitHub issues and PRs", slash: true, run: () => run(openWork) });
      c.tui.command.add("todo", { desc: "save a project task for later", slash: true, args: true, run: (args) => run(async () => addTask(await location(), String(args || "").trim())) });
}
}
  
}
