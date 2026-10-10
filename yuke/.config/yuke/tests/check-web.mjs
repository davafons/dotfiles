#!/usr/bin/env node
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

// Replace only the host import to exercise the real tool code without credentials or network.
const source = await readFile(new URL("../tools/web.js", import.meta.url), "utf8");
const variables = {};
const files = new Map();
const requests = [];
const reads = [];
let response = { status: "COMPLETED", output: { results: [{ title: "Documentation", url: "https://neovim.io/doc/", snippet: "Neovim docs" }] } };
globalThis.webTest = {
  env: { get: (name) => variables[name] },
  fs: {
    stat: async (path) => files.has(path) ? {} : null,
    readFile: async (path) => { reads.push(path); return files.get(path); },
  },
  fetch: async (url, options) => {
    requests.push({ url, ...options });
    return { ok: true, text: async () => JSON.stringify(response) };
  },
};
const code = source.replace('import { fetch, env, fs } from "yuke";', "const { fetch, env, fs } = globalThis.webTest;");
assert.notEqual(code, source, "host import changed; update the test shim");
const { web } = await import("data:text/javascript;base64," + Buffer.from(code).toString("base64"));
const tools = new Map();
web.apply({ tools: { define: (tool) => tools.set(tool.name, tool) } });
assert.deepEqual([...tools.keys()], ["web_search", "web_fetch"]);
const search = (args = { query: "Neovim documentation" }) => tools.get("web_search").execute(args, { aborted: false });
const fetchPage = (args = { url: "https://neovim.io/doc/" }) => tools.get("web_fetch").execute(args, { aborted: false });

variables.HOME = "/test-home";
await assert.rejects(search(), /Set MONID_API_KEY.*\/test-home\/\.config\/yuke\/monid.key/);
assert.equal(requests.length, 0);
files.set("/test-home/.config/yuke/monid.key", "  file-test-key\n");
assert.match(await search(), /Documentation.*\nhttps:\/\/neovim.io\/doc\//);
assert.equal(requests.at(-1).headers.Authorization, "Bearer file-test-key");
assert.deepEqual(JSON.parse(requests.at(-1).body), {
  provider: "tinyfish", endpoint: "/search", input: { queryParams: { query: "Neovim documentation" } },
});

variables.MONID_API_KEY = "  env-test-key  ";
reads.length = 0;
await search();
assert.equal(requests.at(-1).headers.Authorization, "Bearer env-test-key");
assert.equal(reads.length, 0, "environment override should not read the file");
delete variables.MONID_API_KEY;
variables.XDG_CONFIG_HOME = "/custom-config";
variables.YUKE_APPNAME = "test-app";
files.set("/custom-config/test-app/monid.key", "custom-test-key\n");
await search();
assert.equal(reads.at(-1), "/custom-config/test-app/monid.key");
assert.equal(requests.at(-1).headers.Authorization, "Bearer custom-test-key");
files.set("/custom-config/test-app/monid.key", "\n");
await assert.rejects(search(), /Monid key file is empty/);
files.set("/custom-config/test-app/monid.key", "custom-test-key\n");

response = { status: "COMPLETED", output: { results: [{ title: "Documentation", final_url: "https://neovim.io/doc/", text: "# Documentation\n\nNeovim help." }] } };
assert.match(await fetchPage(), /# Documentation\n\nNeovim help/);
assert.deepEqual(JSON.parse(requests.at(-1).body), {
  provider: "tinyfish", endpoint: "/fetch", input: { body: { urls: ["https://neovim.io/doc/"], format: "markdown" } },
});
await assert.rejects(search({ query: " " }), /query is required/);
await assert.rejects(fetchPage({ url: "file:///private" }), /url must be http/);
console.log("Web tool checks passed (private file, environment override, XDG/app paths, search, fetch, and validation).");
