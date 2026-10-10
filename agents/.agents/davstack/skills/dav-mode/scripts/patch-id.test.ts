import { expect, test } from "bun:test";
import { spawnSync } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const checker = join(import.meta.dir, "patch-id.mjs");

function jj(cwd: string, ...args: string[]): string {
  const result = spawnSync("jj", args, { cwd, encoding: "utf8" });
  expect(result.status, result.stderr).toBe(0);
  return result.stdout.trim();
}

function fingerprint(cwd: string, base: string, head: string) {
  return spawnSync("node", [checker, base, head], { cwd, encoding: "utf8" });
}

test("keeps the stable fingerprint through an offset-only rebase, but detects a changed patch", () => {
  const directory = mkdtempSync(join(tmpdir(), "davstack-patch-"));
  try {
    jj(directory, "git", "init", "--no-colocate");
    const file = join(directory, "example.txt");
    const content = Array.from({ length: 25 }, (_, i) => `line ${i}`).join("\n") + "\n";
    writeFileSync(file, content);
    const base = jj(directory, "log", "--no-graph", "-r", "@", "-T", "commit_id");
    jj(directory, "new");
    writeFileSync(file, content.replace("line 15\n", "changed 15\n"));
    const head = jj(directory, "log", "--no-graph", "-r", "@", "-T", "commit_id");
    const change = jj(directory, "log", "--no-graph", "-r", "@", "-T", "change_id");
    const before = fingerprint(directory, base, head);
    expect(before.status, before.stderr).toBe(0);
    expect(before.stdout.trim()).toMatch(/^[0-9a-f]{40,64}$/);
    jj(directory, "new", base);
    writeFileSync(file, `padding\n${content}`);
    const nextBase = jj(directory, "log", "--no-graph", "-r", "@", "-T", "commit_id");
    jj(directory, "rebase", "-r", head, "-d", nextBase);
    const nextHead = jj(directory, "log", "--no-graph", "-r", change, "-T", "commit_id");
    const after = fingerprint(directory, nextBase, nextHead);
    expect(after.status, after.stderr).toBe(0);
    expect(after.stdout).toBe(before.stdout);
    jj(directory, "new", nextHead);
    writeFileSync(file, `padding\n${content.replace("line 15\n", "different 15\n")}`);
    const changed = jj(directory, "log", "--no-graph", "-r", "@", "-T", "commit_id");
    const different = fingerprint(directory, nextBase, changed);
    expect(different.status, different.stderr).toBe(0);
    expect(different.stdout).not.toBe(before.stdout);
    const empty = fingerprint(directory, base, base);
    expect(empty.status, empty.stderr).toBe(0);
    expect(empty.stdout).toBe("empty\n");
    const invalid = fingerprint(directory, "a-revision-that-does-not-exist", changed);
    expect(invalid.status).toBe(2);
    expect(invalid.stdout).toBe("");
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});

test("requires exactly two revisions", () => {
  for (const args of [[], ["@"], ["@", "@", "extra"]]) {
    const result = spawnSync("node", [checker, ...args], { encoding: "utf8" });
    expect(result.status).toBe(2);
    expect(result.stdout).toBe("");
  }
});
