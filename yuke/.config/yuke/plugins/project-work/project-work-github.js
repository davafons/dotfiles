//! Read-only GitHub transport. Network reads stay outside paint and use the caller's cancellation signal.
import { exec } from "yuke";
/** @import { CancellationSignal } from "yuke" */
/** @typedef {{number: number, title: string, url: string, state: string, updated_at: string, author: string, labels: string[], kind: string, draft: boolean, review: string | null, ci: string | null, body: string, checks: {name: string, status: string, url: string}[], more_checks: boolean, head: string, base: string}} GitHubItem */
/** @typedef {{repo: string, repo_url: string, kind: string, fetched_at: number, items: GitHubItem[], total: number, state: string, next_cursor: string, has_next: boolean}} GitHubPage */
/** @typedef {{repo: string, repo_url: string, kind: string, fetched_at: number, item: GitHubItem, linked_tasks: {id: string, title: string, status: string, version: number, github_url: string}[], linked_task_count: number}} GitHubDetail */

/** Read GitHub through the installed helper. The caller owns the decoded result. A null review or CI means GitHub did not report it. Missing gh, failed authentication, unavailable records, and cancellation throw.
 * @param {string} helper @param {string} root @param {Record<string, unknown>} args @param {CancellationSignal} signal
 */
export async function readGitHub(helper, root, args, signal) {
  if (signal.aborted) throw new Error("GitHub read canceled.");
  let output = "";
  const command = ["python3", helper, JSON.stringify({ ...args, root })].map((value) => "'" + value.replaceAll("'", "'\\''") + "'").join(" ");
  const result = await exec(command, { signal, timeoutMs: 60000, mergeStderr: true, onOutput: (chunk) => { output += chunk; } });
  if (result.code !== 0) throw new Error((output || result.stdout || "GitHub read failed.").trim());
  return JSON.parse(output);
}
