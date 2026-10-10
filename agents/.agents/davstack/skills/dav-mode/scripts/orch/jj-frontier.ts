import { execFileSync } from "node:child_process";
import { parseRemote } from "../watch-pr/github.ts";
import type { FrontierPr } from "./store.ts";

function command(repo: string, executable: string, args: string[]): string {
  return execFileSync(executable, args, {
    cwd: repo,
    encoding: "utf8",
    env: { ...process.env },
    stdio: ["ignore", "pipe", "pipe"],
    timeout: 30_000,
    maxBuffer: 64 * 1024 * 1024,
  }).trim();
}

function jj(repo: string, ...args: string[]): string {
  return command(repo, "jj", ["--color", "never", ...args]);
}

function object(value: unknown, label: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error(`${label} is not an object`);
  }
  return value as Record<string, unknown>;
}

export function resolveJjFrontier(repo: string, scope: readonly number[]): readonly FrontierPr[] {
  jj(repo, "root");
  if (scope.length === 0) {
    throw new Error("Set --prs to the program's bottom-to-top PR scope on the first frontier refresh.");
  }
  const origin = jj(repo, "git", "remote", "list").match(/^origin\s+([^\r\n]+)$/m)?.[1];
  const repository = origin === undefined ? null : parseRemote(origin);
  if (repository === null) throw new Error("The jj origin is not a supported GitHub repository.");
  const fields = scope.map((pr) => `p${pr}: pullRequest(number: ${pr}) { number headRefName headRefOid state }`).join("\n");
  const openFields = "open: pullRequests(first: 100, states: OPEN, after: $after) { nodes { number headRefName headRefOid } pageInfo { hasNextPage endCursor } }";
  const query = `query($owner: String!, $repo: String!, $after: String) { repository(owner: $owner, name: $repo) { ${fields} ${openFields} } }`;
  function readRepository(after: string | null): Record<string, unknown> {
    const args = ["api", "graphql", "-f", `query=${query}`, "-f", `owner=${repository!.owner}`, "-f", `repo=${repository!.repo}`];
    if (after !== null) args.push("-f", `after=${after}`);
    const response: unknown = JSON.parse(command(repo, "gh", args));
    return object(object(object(response, "GitHub response").data, "GitHub data").repository, "GitHub repository");
  }
  const prs = readRepository(null);
  const open: Record<string, unknown>[] = [];
  const cursors = new Set<string>();
  let page = prs;
  while (true) {
    const connection = object(page.open, "Open PR snapshot");
    if (!Array.isArray(connection.nodes)) throw new Error("Open PR snapshot has no node list.");
    open.push(...connection.nodes.map((node: unknown) => object(node, "Open PR")));
    const info = object(connection.pageInfo, "Open PR pageInfo");
    if (info.hasNextPage === false) break;
    if (info.hasNextPage !== true || typeof info.endCursor !== "string" || !info.endCursor || cursors.has(info.endCursor)) throw new Error("Open PR pagination is incomplete or repeats a cursor.");
    cursors.add(info.endCursor);
    page = readRepository(info.endCursor);
  }
  const rows: FrontierPr[] = scope.map((pr) => {
    const data = object(prs[`p${pr}`], `PR ${pr}`);
    const { number, headRefName, headRefOid, state } = data;
    if (number !== pr || typeof headRefName !== "string" || typeof headRefOid !== "string" || !/^(?:[0-9a-f]{40}|[0-9a-f]{64})$/i.test(headRefOid) || !(state === "OPEN" || state === "CLOSED" || state === "MERGED")) {
      throw new Error(`PR ${pr} has invalid frontier metadata.`);
    }
    const sha = jj(repo, "log", "--no-graph", "-r", `bookmarks(exact:${JSON.stringify(headRefName)})`, "-T", "commit_id");
    if (sha !== headRefOid) throw new Error(`PR ${pr}: jj bookmark ${headRefName} does not match the forge head. Fetch or reconcile the owner's reported tip before refreshing.`);
    return { pr, branches: headRefName, sha, state };
  });
  if (new Set(rows.map((row) => row.sha)).size !== rows.length) throw new Error("Selected PR bookmarks share a head; the stack is not strictly linear.");
  const selected = `(${rows.map((row) => row.sha).join(" | ")})`;
  const ancestors = new Map(rows.map((row) => [row.sha, new Set(jj(repo, "log", "--no-graph", "-r", `${selected} & ancestors(${row.sha})`, "-T", 'commit_id ++ "\\n"').split("\n"))]));
  rows.sort((a, b) => ancestors.get(a.sha)!.size - ancestors.get(b.sha)!.size);
  for (let i = 1; i < rows.length; i++) {
    if (!ancestors.get(rows[i].sha)!.has(rows[i - 1].sha)) throw new Error("Selected PR bookmarks are not a linear jj stack. Do not infer topology from forge base refs.");
  }
  const trunk = jj(repo, "log", "--no-graph", "-r", "coalesce(present(main@origin), main)", "-T", "commit_id");
  for (const data of open) {
    const { number, headRefName, headRefOid } = data;
    if (typeof number !== "number" || !Number.isSafeInteger(number) || number <= 0 || typeof headRefName !== "string" || typeof headRefOid !== "string") throw new Error("Open PR has invalid identity or head metadata.");
    if (scope.includes(number)) {
      if (rows.find((row) => row.pr === number)?.sha !== headRefOid) throw new Error(`PR ${number} moved during the frontier snapshot.`);
      continue;
    }
    const local = jj(repo, "log", "--no-graph", "-r", `bookmarks(exact:${JSON.stringify(headRefName)})`, "-T", "commit_id");
    if (!local) continue;
    if (!/^(?:[0-9a-f]{40}|[0-9a-f]{64})$/i.test(local)) throw new Error(`PR ${number} has a conflicted jj bookmark.`);
    const related = jj(repo, "log", "--no-graph", "-r", `${local} & (ancestors(${rows.at(-1)!.sha}) | descendants(${rows[0].sha})) ~ ancestors(${trunk})`, "-T", "commit_id");
    if (related) throw new Error(`PR ${number} is a tracked member of this jj stack but is missing from --prs. Refresh the complete program scope before accepting the frontier.`);
  }
  return rows;
}
