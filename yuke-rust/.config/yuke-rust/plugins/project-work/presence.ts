import type { Sessions } from "yuke:plugins";

/** The presence arguments of the work store: the native tree root of each owner, and the sessions open here. */
export interface Owners {
  readonly roots: Record<string, string>;
  readonly open_sessions: string[];
}

/**
 * Walk each assigned session to its native tree root. The store checks the lock of each root and the Herdr
 * inventory. An owner that the session store cannot find gets no root, so its claim stays.
 */
export async function owners(sessions: Sessions, ids: Iterable<string>, signal: AbortSignal): Promise<Owners> {
  const roots: Record<string, string> = {};
  const open = new Set<string>();
  for (const owner of new Set(ids)) {
    if (owner === "") continue;
    try {
      let id = owner;
      for (let depth = 0; depth < 64; depth += 1) {
        const row = await sessions.get(id);
        if (row.state !== "closed") open.add(row.sessionId);
        if (row.parent === undefined) break;
        id = row.parent;
      }
      roots[owner] = id;
    } catch (error) {
      if (signal.aborted) throw error;
    }
  }
  return { roots, open_sessions: [...open] };
}
