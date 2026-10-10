# Multi-phase or multi-PR plan

Read [Playbook runtime](../references/playbook-runtime.md) before executing these steps.

**You own the plan, not the code. The plan is a checklist an owner runs box by box and the operator audits from the evidence.** The plan is the deliverable. Do not implement.

1. When the change is one or two files with an obvious approach, skip the plan. Say so and stop.
2. Settle open questions by prototype before you write. Run the [Prototype playbook](prototype.md) for each. Keep the branch, the SHA, and the screenshots for Appendix A. Ask the operator only about a product or preference call that no run can settle. Give options (the [never-block-on-the-human principle](https://github.com/cursor/plugins/blob/1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def/pstack/skills/principle-never-block-on-the-human/SKILL.md)).
3. Explore through the current harness's configured agents and models when delegation is authorized (the [guard-the-context-window principle](https://github.com/cursor/plugins/blob/1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def/pstack/skills/principle-guard-the-context-window/SKILL.md)). Each returns file pointers, conventions, test commands, and entry points. No inlined dumps.
4. Copy the skeleton below into the plan file and fill every placeholder. Use the operator's path or the project's plan directory. If neither supplies one, use `docs/<program>-plan.md`. Keep every heading and every sub-block in the order shown. One section per PR. One PR is one change with its own evidence (the [sequence-verifiable-units principle](https://github.com/cursor/plugins/blob/1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def/pstack/skills/principle-sequence-verifiable-units/SKILL.md)). Name the supported execution workflow in **How to read this**. Preserve the distinction between independent PRs delivered to merge, a linear reviewed stack delivered for the operator to land, and a standing coordinated program. The upstream [Autopilot-full](https://github.com/cursor/plugins/blob/1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def/pstack/skills/poteto-mode/playbooks/autopilot-full.md), [Autopilot-stack](https://github.com/cursor/plugins/blob/1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def/pstack/skills/poteto-mode/playbooks/autopilot-stack.md), and [Orchestrate](https://github.com/cursor/plugins/blob/1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def/pstack/skills/poteto-mode/playbooks/orchestrate.md) protocols describe those choices; they are not installed here. Name missing capabilities before proposing execution.
5. Write under [the installed writing reference](../../technical-writing/SKILL.md), then [unslop](../../unslop/SKILL.md). The body is one Diátaxis mode, how-to. Appendices hold explanation and reference. Each heading states the task or the finding. No long dashes. No mid-sentence colons.
6. Run the project's plan validator and fix every diagnostic. If no validator exists, inspect every required heading, block, and evidence predicate in the skeleton and report automated validation as a gap, not a passed check (the [encode-lessons-in-structure principle](https://github.com/cursor/plugins/blob/1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def/pstack/skills/principle-encode-lessons-in-structure/SKILL.md)).
7. Hand back. Post the plan path and the validator's output or explicit validation gap, then stop. Execution starts on the operator's explicit go, under the supported execution workflow the plan names.

**Verification.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked (the [prove-it-works principle](https://github.com/cursor/plugins/blob/1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def/pstack/skills/principle-prove-it-works/SKILL.md)). That sentence is the verification rule. Every verification block opens with it. The live block is mandatory. Ten lanes at the PR head drive the real surface through its matching verification/control workflow, per the [swarm protocol](https://github.com/cursor/plugins/blob/1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def/pstack/skills/swarm/SKILL.md), using the configured verification-worker model. Each lane is one box with a concrete scenario, the screenshot it saves, and its pass predicate. One lane is the **Regression lane against trunk.** It runs the same load-bearing scenario on trunk and head. If trunk does not have the feature, the lane records that fact and gates the behavior the diff adds plus the end state the user waits for instead of inventing a trunk result. The perf gate is dual-sided. Trunk and head must both produce the named metric. If trunk lacks the feature, also isolate the work the diff adds and set an absolute budget for that work plus the end-to-end state the user waits for. Do not claim a ratio between unlike scenarios. The perf block names the metric, the interleaved probe, the trunk baseline measured first, and the rule with the number that fails. A PR that changes an interaction is review-gated. The operator reviews it in chat with screenshots and a video before merge. A PR that changes no interaction writes `**Review gate.** None. <PR id> is not review-gated.` and no boxes under it.

**Control workflow.** Pick it by surface. Use the configured browser or UI control workflow for browser, Electron, and web UIs; use the project's CLI/TUI driver for terminal surfaces. Native mobile uses the project's simulator-driving workflow with applicable desktop authority. A PR that touches two surfaces gets lanes on both. A surface with no proven driver is a risk in Appendix C, and its live block still names how each lane drives it.

````markdown
# <Program> plan

<Under ten lines. What changes, for whom, the rule the program enforces, and the PR ids in order.>

## How to read this

One box is one unit of work. Every box names the evidence that checks it. A nested box is a sub-step of the box above it. Check a box only when its evidence exists, a file, a log line, a screenshot, a test run, or a SHA. The body is a how-to. The appendices explain and record.

The program runs `<supported execution workflow path or protocol URL>`. <Who merges, and which PR ids are the operator's items that stop at merge-ready.>

Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

## Program checklist

### Arm the program

- [ ] State the protocol and this plan to the operator, then stop. Start execution only on the operator's explicit go.
- [ ] Read the project-owned workflows from current trunk at program start using native version-control file reads, and the installed or pinned source for external protocols. Re-read them at every tick.
  - [ ] Read `<supported execution workflow path or protocol URL>`.
  - [ ] Read the [swarm protocol](https://github.com/cursor/plugins/blob/1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def/pstack/skills/swarm/SKILL.md) and the runtime delegation rules in `~/.agents/skills/dav-mode/references/playbook-runtime.md`.
  - [ ] Read `<matching verification/control workflow path>`.
  - [ ] Read the PR handoff in `~/.agents/skills/dav-mode/references/playbook-runtime.md` and the project's approved PR workflow.
  - [ ] Read each other installed skill or pinned protocol the program uses.
- [ ] On the operator's go, arm the hourly audit tick through an available, authorized scheduler with the tick prompt below. Never leave the cadence to memory. If persistent scheduling is unavailable, report the gap and leave automatic execution unarmed.
- [ ] Use this tick prompt, verbatim. "Re-read the execution playbook from trunk. Audit the operation against it and fix drift in this tick. Probe every active lane and judge progress by side effects only. Stand down a stuck lane and dispatch its replacement now. Then post a short status message to the operator in chat only when the audit found a tracked change that no earlier status message reported, such as a PR opened, a code-ready head, a round launched or closed, a verdict, a merge, a stuck agent and the action taken, a blocker added or cleared, or a decision only the operator can make. Name every such change and nothing else. Do not repeat a table, the merged list, or an unchanged blocker. If the audit found none, end the turn with no reply text. Either way, log this tick's row in your decision trail. The row names the items reported, or none."
- [ ] On the operator's hold or stand-down, send every owner a zero-writes order at once.

### Spawn owners

- [ ] Spawn one owner per PR with the full lifecycle the execution playbook names.
- [ ] Follow this dependency graph. Start dependent work only after its parent merges, or base it on the parent branch when the execution playbook stacks.
  - [ ] <PR id> and <PR id> are independent and first. Both branch from `main`.
  - [ ] <PR id> after <PR id>.
- [ ] Hold the file boundaries. <PR id or class> touches only `<glob>`.
- [ ] Hold the review gate. <PR ids> change an interaction. They wait for the operator's review in chat with screenshots and a video before merge.

### PR mechanics, for every PR

- [ ] Resolve the forge once. Default to `gh`; if `command -v origin` succeeds and Origin can resolve the repository, use `origin pr` for every PR operation. Record any fallback to `gh`. Never require `gt`.
- [ ] Open the PR ready, never draft, per the PR handoff in `~/.agents/skills/dav-mode/references/playbook-runtime.md`. Use the run's built-in PR tool when it has one, else `origin pr create --status open --base <base-branch>` or `gh pr create --base <base-branch>` according to the resolved forge. A stack child targets its parent branch.
- [ ] Run the repo's lint and typecheck once before the PR-facing push. Push through the project's approved formatter, lint, and pre-push workflow; do not assume Git hooks run in jj.
- [ ] Run the project's code-quality checks before each scoped change and the no-comments skill at `~/.agents/skills/no-comments/SKILL.md` before review.
- [ ] Triage every automated code/security-review comment against the source and evidence. Fix real defects, dismiss non-issues with a concrete reason, and ask only for decisions the operator must make.
- [ ] Rebase onto current trunk before the code-ready report and PR-status driving. Keep that merge base in fix rounds. Rebase again only at merge prep, on a native conflict check with trunk, or on a CI failure that comes from a change on trunk.

### Verdict and merge, for every PR

- [ ] At the code-ready head SHA and at each later push that changes the patch, run the coverage matrix per the [swarm protocol](https://github.com/cursor/plugins/blob/1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def/pstack/skills/swarm/SKILL.md) through authorized native agents. One gates lane. The ten live lanes from the PR's **Verify, live** block. The perf lane from its **Verify, perf** block. Two or more audit lanes, each with its own focus, that read the diff and the receipts and distrust the PR body. The root audits the receipts in the merge-ready report before the verdict.
- [ ] Clean only when every lane is `PASS`. Findings go back to the owner, including a defect that a lane filed as a note. A new head gets a fresh coverage run and a fresh verdict, except for results that stay valid under the patch-id rule in `~/.agents/skills/dav-mode/playbooks/shipping.md`.
- [ ] <The merge or append rule from the execution playbook, with the patch-id rule from `~/.agents/skills/dav-mode/playbooks/shipping.md`.>

### Boot recipe, for every live lane

Each live lane runs in its own available isolated test environment at the exact PR head. Drive through the project's matching verification/control workflow.

- [ ] Fetch `<head-branch>` through native version control, then create or select the lane's isolated checkout at `<head SHA>`. In jj use `jj git fetch --branch <head-branch>` and `jj new <head SHA>` inside that lane's own workspace, not the user's active checkout.
- [ ] <Start the backend and the surface. Wait for ready.>
- [ ] <Deliver input only through the supported control workflow's commands. Name the read-only diagnostics.>
- [ ] Save every screenshot to `/tmp/swarm-<pr-id>/worker-<n>/<slug>.png` and return the paths with the report.

## <Task as a verb phrase> (<PR id>)

**Depends on.** <PR id, or None.>

**Files.**

- [ ] Edit `<path>`.
- [ ] Create `<path>`.
- [ ] Delete `<path>`.

**Build.**

- [ ] <One change. Name the symbol and the file.>

**You see.**

- [ ] <One observable result, with the exact log line or screen state.>

**Verify, unit.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] <Test file and the case it gains.> Run `<command>`.

**Verify, live.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. Ten lanes on `<configured verification-worker model>` at the PR head, per the boot recipe.

- [ ] Lane 1. Regression lane against trunk. Run <the same load-bearing scenario> at trunk and head. If trunk lacks the feature, record that and gate <the behavior the diff adds plus the end state the user waits for>. Save `<slug>.png`. Pass when <predicate>.
- [ ] Lane 2. <Scenario.> Save `<slug>.png`. Pass when <predicate>.
- [ ] Lane 3. <Scenario.> Save `<slug>.png`. Pass when <predicate>.
- [ ] Lane 4. <Scenario.> Save `<slug>.png`. Pass when <predicate>.
- [ ] Lane 5. <Scenario.> Save `<slug>.png`. Pass when <predicate>.
- [ ] Lane 6. <Scenario.> Save `<slug>.png`. Pass when <predicate>.
- [ ] Lane 7. <Scenario.> Save `<slug>.png`. Pass when <predicate>.
- [ ] Lane 8. <Scenario.> Save `<slug>.png`. Pass when <predicate>.
- [ ] Lane 9. <Scenario.> Save `<slug>.png`. Pass when <predicate>.
- [ ] Lane 10. <Scenario.> Save `<slug>.png`. Pass when <predicate>.

**Verify, perf.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] Metric. <What is measured at both trunk and head. If trunk lacks the feature, also name the diff-added work and the end-to-end state the user waits for.>
- [ ] Probe. <The command or procedure, run at trunk and at the head, interleaved. Both sides must produce the metric.>
- [ ] Baseline. Record the trunk <value> first.
- [ ] Rule. <Head against trunk, with the number that fails. If the scenarios differ, add absolute budgets for the diff-added work and the user-visible end state instead of an invalid ratio.>

**Review gate.** The operator reviews before merge.

- [ ] Copy lane <n> screenshots into `<media path>/<pr-id>-review-<slug>.png`.
- [ ] Record a 30 to 60 second video of the change in a lane's isolated test environment. Save it as `<media path>/<pr-id>-review.mp4`.
- [ ] Post the screenshots and the video in chat. Stop at merge-ready. Wait for the operator's click.

**Merge.**

- [ ] Root's clean verdict at the exact head SHA.
- [ ] Automated code and security review triage done.
- [ ] Rebased onto current trunk after the verdict, patch-id unchanged.
- [ ] <The owner squash-merges its own PR, or the root appends it to the base-branch stack and the operator lands it bottom-up.>

## Close the program

- [ ] Every box above is checked with its evidence.
- [ ] Reply to the operator with the report the execution playbook names.

## Appendix A. Prototype evidence

<Each open question a prototype answered, with the branch, the SHA, and the artifact links. Each question that stays unproven.>

## Appendix B. Alternatives rejected

<Each approach weighed and why it lost.>

## Appendix C. Risks

<Each risk with the PR it lands in and what the owner watches.>

## Appendix D. Links and reading list

<Docs to read before editing. Which PRs need how and the upstream interrogate protocol. The decision trail and the pinned protocol links used by this plan.>
````

**Reply:** the plan path, the PR ids with their dependencies and the review-gated set, what the prototypes proved and what stays unproven, and the validator's output or explicit validation gap.
