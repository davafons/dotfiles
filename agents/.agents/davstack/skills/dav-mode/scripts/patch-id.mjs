#!/usr/bin/env node
import { spawnSync } from "node:child_process";

const [base, head, ...extra] = process.argv.slice(2);
if (!base || !head || extra.length) {
  console.error("Usage: node patch-id.mjs <base> <head>");
  process.exit(2);
}

function run(command, args, input) {
  const result = spawnSync(command, args, {
    encoding: "utf8",
    input,
    maxBuffer: 64 * 1024 * 1024,
  });
  if (result.error || result.status !== 0) {
    console.error(result.error?.message || result.stderr || `${command} exited ${result.status}`);
    process.exit(2);
  }
  return result.stdout;
}

run("jj", ["root"]);
const patch = run("jj", ["diff", "--git", "--from", base, "--to", head]);
const fingerprint = run("git", ["patch-id", "--stable"], patch).trim();
if (!patch.trim()) {
  console.log("empty");
} else if (/^[0-9a-f]{40,64} [0-9a-f]{40,64}$/.test(fingerprint)) {
  console.log(fingerprint.split(" ")[0]);
} else {
  console.error("The patch fingerprint was not a single stable patch ID.");
  process.exit(2);
}
