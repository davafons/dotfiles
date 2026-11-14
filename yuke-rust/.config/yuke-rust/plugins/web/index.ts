import { readTextFile } from "yuke:fs";
import type { SessionContext } from "yuke:plugins";
import { env } from "yuke:process";

const API = "https://api.monid.ai";
const RESULTS = 5;
const PAGE = 4000;

function object(value: unknown): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new TypeError("Monid returned a value that is not an object.");
  }
  return value as Record<string, unknown>;
}

function text(value: unknown): string {
  return typeof value === "string" ? value : "";
}

async function request(path: string, signal: AbortSignal, payload?: unknown): Promise<Record<string, unknown>> {
  const home = env.get("HOME");
  const config = env.get("XDG_CONFIG_HOME") ?? `${home}/.config`;
  const key =
    env.get("MONID_API_KEY")?.trim() ??
    (await readTextFile(`${config}/${env.get("YUKE_APPNAME") ?? "yuke"}/monid.key`, { signal })).trim();
  if (key === "") throw new Error("The Monid API key is empty.");
  const response = await fetch(`${API}${path}`, {
    method: payload === undefined ? "GET" : "POST",
    headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
    ...(payload === undefined ? {} : { body: JSON.stringify(payload) }),
    signal: AbortSignal.any([signal, AbortSignal.timeout(120_000)]),
  });
  if (!response.ok) throw new Error(`Monid HTTP ${response.status}`);
  return object(await response.json());
}

async function run(endpoint: string, input: unknown, signal: AbortSignal): Promise<Record<string, unknown>> {
  let job = await request("/v1/run", signal, { provider: "tinyfish", endpoint, input });
  for (let count = 0; count < 30 && job.status && job.status !== "COMPLETED"; count += 1) {
    if (["FAILED", "BLOCKED", "STOPPED", "TIMED_OUT"].includes(text(job.status)))
      throw new Error(`Monid ${job.status}`);
    const id = text(job.runId);
    if (!/^[A-Za-z0-9]+$/.test(id)) throw new Error("Monid did not return a run ID.");
    await new Promise<void>((resolve, reject) => {
      signal.throwIfAborted();
      const aborted = (): void => {
        clearTimeout(timer);
        reject(signal.reason);
      };
      const timer = setTimeout(() => {
        signal.removeEventListener("abort", aborted);
        resolve();
      }, 2000);
      signal.addEventListener("abort", aborted, { once: true });
    });
    job = await request(`/v1/runs/${id}`, signal);
  }
  if (job.status && job.status !== "COMPLETED") throw new Error(`Monid ${String(job.status)}`);
  return object(job.output);
}

/** Register web search and page retrieval in every session. HTTP, key, cancellation, and response errors fail the call. */
export function session(s: SessionContext): undefined {
  s.tools.add({
    name: "web_search",
    description: "Live web search. Titles, URLs, and short snippets. Use web_fetch for page text.",
    concurrency: "parallel",
    inputSchema: { type: "object", properties: { query: { type: "string" } }, required: ["query"] },
    execute: async (args, context) => {
      if (args.query.trim() === "") throw new Error("query is required");
      const output = await run("/free/search", { queryParams: { query: args.query } }, context.signal);
      if (!Array.isArray(output.results)) throw new Error("Monid returned no results array.");
      return (
        output.results
          .slice(0, RESULTS)
          .map((value: unknown, index: number) => {
            const hit = object(value);
            return `${index + 1}. ${text(hit.title).slice(0, 140)}\n${text(hit.url)}\n${text(hit.snippet).slice(0, 140)}`;
          })
          .join("\n\n") || "No results."
      );
    },
  });
  s.tools.add({
    name: "web_fetch",
    description: "Fetch an HTTP or HTTPS URL as Markdown. Long pages are truncated.",
    concurrency: "parallel",
    inputSchema: { type: "object", properties: { url: { type: "string" } }, required: ["url"] },
    execute: async (args, context) => {
      const url = new URL(args.url);
      if (url.protocol !== "https:" && url.protocol !== "http:") throw new Error("url must be HTTP or HTTPS");
      const output = await run("/free/fetch", { body: { urls: [args.url], format: "markdown" } }, context.signal);
      if (!Array.isArray(output.results) || output.results.length === 0) throw new Error("Monid returned no page.");
      const page = object(output.results[0]);
      const body = text(page.text)
        .replace(/\n{3,}/g, "\n\n")
        .trim();
      return `${text(page.title)}\n${text(page.final_url) || text(page.url)}\n${body.slice(0, PAGE)}${body.length > PAGE ? "\n\n[truncated]" : ""}`;
    },
  });
}
