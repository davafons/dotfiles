//! Share session discovery and ownership checks between native profile browsers.
import { client, env, exec, fs } from "yuke";
import { currentPane, sessions, showSession } from "yuke:session";
import { focusHerdrSession } from "../plugins/herdr/index.js";
const PAGE_LIMIT = 100;
const MAX_PAGES = 1000;
const LOCK_PROBE = `
import fcntl
import os
import sys

root = sys.argv[1]
for session_id in sys.argv[2:]:
    path = os.path.join(root, session_id + ".lock")
    if not os.path.exists(path):
        continue
    try:
        lock = open(path, "a+b")
    except OSError:
        continue
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print(session_id)
    finally:
        lock.close()
`;

/** Resolve the directory Yuke was launched in for a draft with no current session. @returns {Promise<string | null>} */
export async function launchWorkspace() {
  try {
    const directory = await fs.stat(".");
    return directory?.isDirectory ? directory.path : null;
  } catch {
    return null;
  }
}

/** Quote one argument for the host shell. @param {string} value @returns {string} */
function shellArg(value) {
  return "'" + value.replaceAll("'", "'\"'\"'") + "'";
}

/** Resolve the sibling directory that holds the durable session ownership locks. @returns {string | null} */
function ownerDirectory() {
  const home = env.get("HOME");
  const base = env.get("XDG_DATA_HOME") || (home ? home + "/.local/share" : "");
  if (!base) return null;
  return base.replace(/\/+$/, "") + "/" + (env.get("YUKE_APPNAME") || "yuke") + "/yuke.db.owners";
}

/** Find whether each session is closed, open here, or open in another Yuke process. @param {Wire.SessionListItem[]} items @param {import("yuke").CancellationSignal} [signal] @returns {Promise<Map<string, "closed" | "here" | "elsewhere">>} */
export async function sessionOwnership(items, signal) {
  /** @type {Map<string, "closed" | "here" | "elsewhere">} */
  const ownership = new Map(items.map((item) => [item.session.id, "closed"]));
  const heldHere = new Set(sessions.map((session) => session.sessionId).filter((id) => id !== null));
  for (const id of heldHere) ownership.set(id, "here");
  const directory = ownerDirectory();
  if (!directory || items.length === 0) return ownership;
  const command = ["python3", "-c", LOCK_PROBE, directory, ...items.map((item) => item.session.id)].map(shellArg).join(" ");
  const result = await exec(command, { timeoutMs: 5000, signal });
  if (result.code !== 0) throw new Error("Cannot inspect session owners: " + (result.stderr.trim() || "lock probe exited " + result.code));
  for (const id of result.stdout.split(/\r?\n/).filter(Boolean)) {
    ownership.set(id, heldHere.has(id) ? "here" : "elsewhere");
  }
  return ownership;
}

/** Read every top-level session page. Child agent sessions stay in the agent picker. @returns {Promise<Wire.SessionListItem[]>} */
export async function listSessions() {
  /** @type {Wire.SessionListItem[]} */
  const items = [];
  const cursors = new Set();
  /** @type {string | undefined} */
  let cursor;
  for (let pageIndex = 0; pageIndex < MAX_PAGES; pageIndex++) {
    const page = await client.sessionList({ population: { type: "top_level" }, limit: PAGE_LIMIT, ...(cursor ? { cursor } : {}) });
    items.push(...page.items);
    if (!page.next_cursor) return items;
    if (cursors.has(page.next_cursor)) throw new Error("The session page cursor did not advance.");
    cursors.add(page.next_cursor);
    cursor = page.next_cursor;
  }
  throw new Error("The session list exceeds " + MAX_PAGES + " pages.");
}

/** Open a session here or focus its Herdr owner. Recheck ownership at selection; failures keep the browser open. @param {Wire.SessionListItem} item @param {Pick<import("yuke").Context, "alive" | "signal">} ctx @returns {Promise<void>} */
export async function navigateSession(item, ctx) {
  const owners = await sessionOwnership([item], ctx.signal);
  if (!ctx.alive) throw new Error("Search closed.");
  if (owners.get(item.session.id) === "elsewhere") {
    await focusHerdrSession(item.session.id, ctx.signal);
    return;
  }
  const pane = currentPane();
  if (!pane) throw new Error("No chat pane has focus.");
  showSession(pane, item.session.id);
  if (pane.session.sessionId !== item.session.id) throw new Error("The session could not be opened.");
}
