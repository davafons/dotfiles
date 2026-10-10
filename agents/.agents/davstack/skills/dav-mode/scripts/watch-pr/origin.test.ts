import { expect, test } from "bun:test";
import { spawnSync } from "node:child_process";
import { existsSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const reader = join(import.meta.dir, "github.ts");

function jj(cwd: string, ...args: string[]): void {
  const result = spawnSync("jj", args, { cwd, encoding: "utf8" });
  expect(result.status, result.stderr).toBe(0);
}

for (const colocated of [false, true]) {
  test(`reads the origin with jj in a ${colocated ? "colocated" : "non-colocated"} repository`, () => {
    const directory = mkdtempSync(join(tmpdir(), "davstack-origin-"));
    try {
      jj(directory, "git", "init", colocated ? "--colocate" : "--no-colocate");
      jj(directory, "git", "remote", "add", "upstream", "https://github.com/not/the-origin.git");
      jj(directory, "git", "remote", "add", "origin", "git@github.com:owner/project.git");
      const git = join(directory, "git");
      const called = join(directory, "git-called");
      writeFileSync(git, `#!/bin/sh\nprintf called > ${JSON.stringify(called)}\nexit 99\n`, { mode: 0o755 });
      const result = spawnSync(process.execPath, ["--eval", `import { GhGitHubReader } from ${JSON.stringify(reader)}; console.log(JSON.stringify(await new GhGitHubReader().originRepo()));`], {
        cwd: directory,
        env: { ...process.env, PATH: `${directory}:${process.env.PATH}` },
        encoding: "utf8",
      });
      expect(result.status, result.stderr).toBe(0);
      expect(JSON.parse(result.stdout)).toEqual({ owner: "owner", repo: "project" });
      expect(existsSync(called)).toBe(false);
    } finally {
      rmSync(directory, { recursive: true, force: true });
    }
  });
}

test("returns no inferred repository when origin is absent", () => {
  const directory = mkdtempSync(join(tmpdir(), "davstack-origin-"));
  try {
    jj(directory, "git", "init", "--no-colocate");
    jj(directory, "git", "remote", "add", "upstream", "https://github.com/not/the-origin.git");
    const result = spawnSync(process.execPath, ["--eval", `import { GhGitHubReader } from ${JSON.stringify(reader)}; console.log(JSON.stringify(await new GhGitHubReader().originRepo()));`], { cwd: directory, encoding: "utf8" });
    expect(result.status, result.stderr).toBe(0);
    expect(JSON.parse(result.stdout)).toBeNull();
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});
