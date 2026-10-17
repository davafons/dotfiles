---
name: swarm
description: "Fan out N parallel workers, drain them, and return one report. Use for /swarm, 'swarm this', or parallel coverage, races, gauntlets, and exploration."
disable-model-invocation: true
license: MIT
metadata:
  upstream: https://github.com/cursor/plugins/tree/1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def/pstack/skills/swarm
  revision: 1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def
---

# Swarm

## Runtime adaptation

Read the [shared working rules](../dav-mode/references/working-rules.md) and
[native coordination contract](../dav-mode/references/playbook-runtime.md#design-and-coordination).
They govern tools, model roles, workspace ownership, and authority throughout
this method. Preserve every phase and required output. Missing independent
workers, a judge, or safe output isolation leaves that gate open, not passed.
Installing this skill does not authorize delegation, model trials, or publication.

Fan out N authorized parallel workers through the native harness. They may cover separate slices, race the same brief, or mix both. The parent waits, aggregates, and returns one report.

## Start

Open a todolist with one entry per phase before launching anything.

1. Frame
2. Fan out
3. Aggregate
4. Report

## Phase A: Frame

1. State the done predicate and the artifact or report the swarm must return.
2. Choose the shape. Partition into slices, race N workers on identical briefs, or mix both. For a race or mixed shape, declare `first pass`, `rank all`, or `best-of` before spawning.
3. Set N from the user or derive it from the shape. N is total workers, not the cloud concurrency limit.
4. Pick the workers from the current harness's configured roles under the native coordination contract. Use inherited settings only when the selected role actually inherits them. For a model race, name each arm's model up front and confirm it from engine receipts. A missing required model leaves that arm blocked; do not silently replace it.
5. Give each worker its own writable output when it writes. When workers verify or measure commits, each brief names the exact SHAs. A measurement brief also names the method (sample count, what one sample is, order). The worker records both in its result.

## Phase B: Fan out

Dispatch all N workers through supported native fan-out calls with the step 4 roles, then end the turn and wait for their terminal reports as the harness requires. Use available local or isolated environments; cloud workers are not required. Keep the declared parallel shape. If dispatch cannot provide it, report the gap rather than claiming sequential work was a swarm.

When a worker needs a non-default revision, name the exact revision and owned checkout in its brief. Verify its actual file and command roots under the native coordination contract. Do not push a branch merely to start a worker.

Every brief stands alone. Include the goal, scope, exact slice or race arm, how to verify, and what to report. Reports use `PASS`, `ISSUES`, or `BLOCKED` with evidence. A worker that can prove a defect reports `ISSUES` and lists every issue it can prove, not only the first.

If a worker drops out, proceed with N-1 and note it.

## Phase C: Aggregate

Read the terminal results. Drop a result that does not record the SHAs and method its brief names, and respawn that worker once. After a second miss, record a gap. A gap does not count as a pass. For coverage, every required slice needs a result. For a race, apply the selection rule declared up front. Use first pass, rank all, or best-of. Do not paste raw worker dumps.

Keep a compact result table, one-line evidenced issues, and explicit gaps or dropouts.

## Phase D: Report

Return one consolidated in-chat report with the table, issue one-liners, gaps or dropouts, and the race rule when used.
