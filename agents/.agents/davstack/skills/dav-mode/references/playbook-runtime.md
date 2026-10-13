# Playbook runtime

Read the [shared working rules](working-rules.md). User and runtime instructions
outrank a playbook. Keep its method and verification gates; adapt its tools,
not its purpose. A missing capability is a reported gap, not a passing result.

## Source

The 23 selected playbooks are adapted from
[cursor/plugins pstack at `1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def`](https://github.com/cursor/plugins/tree/1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def/pstack/skills/poteto-mode/playbooks).
The upstream [MIT license](../LICENSE) accompanies them. Source URLs identify
upstream; they do not require its editor or install its other workflows.

## Delegation and models

Use the current harness's child API and configured agent/model roles. Inherit
the configured agent defaults when no role-specific model exists. Do not
assume per-call model selection, cloud workers, background execution, or nested
delegation. Follow the actual start, wait, follow-up, and stop lifecycle.
Delegation still requires an explicit user request.

Without authorized delegation, do the permitted work directly and disclose the
missing independent perspective. A serial self-review does not satisfy an
independent verification or cross-model judging gate. Leave that gate open.
Never label a different-model-family run successful when that model was unavailable.

Give delegates scoped briefs, ownership boundaries, verification requirements,
and the shared-desktop restrictions. Inspect their artifacts before accepting
results. The parent owns the workflow, not merely the delegates' summaries.

## Workflow dependencies

Links to upstream `architect`, `arena`, `swarm`, `interrogate`, and
`principle-*` files are protocol
references, not installed skills. Read the relevant source when its method is
required. Apply that method through available tools and the shared rules.
Do not invent an invocation, silently install a dependency, or claim that reading
its instructions executed it.

Preserve the method's required outputs: distinct design candidates and synthesis,
blinded judging, lane coverage, measurement vetting, and decision evidence.
Report unavailable automation or independent roles. Keep required gates open
when they cannot be satisfied; do not weaken them to match the available tools.

The [benchmark-checklist](../../benchmark-checklist/SKILL.md) and
[show-me-your-work](../../show-me-your-work/SKILL.md) skills are installed locally.
The latter owns the decision-log format and its executable logger. Its independent
cross-model review remains a separate permission and capability gate.

For document writing, use [the installed writing reference](../../technical-writing/SKILL.md)
and [unslop](../../unslop/SKILL.md). Follow the project's plan and evidence locations.
The installed execution playbooks include [Autonomous run](../playbooks/autonomous-run.md),
[Autopilot-full](../playbooks/autopilot-full.md), [Autopilot-stack](../playbooks/autopilot-stack.md),
[Orchestrate](../playbooks/orchestrate.md), and [Babysit](../playbooks/babysit.md).
Name the supported execution workflow and its gaps before asking to start it.

## Control surfaces and loops

The installed [control-cli](../../control-cli/SKILL.md) owns generic terminal
driving. [create-verification-skill](../../create-verification-skill/SKILL.md)
generates project drivers and maps;
[maintain-verification-skill](../../maintain-verification-skill/SKILL.md) audits
their source and live coverage. Use the project's verification/control skill or a proven CLI, API, browser, or
computer-use workflow for the matching surface. This local computer is available
for testing; a cloud worker is not required. Local execution and model-backed
execution are separate choices. A model-free verification run means no additional
model calls, not that computer-use tools are unavailable. Do not substitute a unit test for the original
live reproduction. Apply desktop permissions before instrumentation or GUI work.
A live hotfix also needs applicable authority; diagnosis does not authorize
production mutation.

Use the installed [loop skill](../../loop/SKILL.md) and an available, authorized
native scheduler for recurring agent turns. The Yuke adapter is session-bound.
Quit or profile reload stops its timers, and restarting requires explicit
rearming. It has no daemon or saved schedule. A foreground iteration is not a
scheduled agent turn. If no native scheduler is available, report the gap and
leave the cadence unarmed. Save a checkpoint at the safe boundary.

Read only the named session's history through an authorized current-harness API
or export. Never assume another editor's transcript paths or search unrelated chats.

## Version control and durable state

These workflows target jj repositories. Confirm `jj root` succeeds before
version-control commands. Use jj for history, workspaces, bookmarks, rebases,
and pushes. If jj is unavailable, report that runtime gap rather than switching
to Git. Follow project branch and push rules.
A shared working copy must not be described, split, or rebased as if all its
changes belonged to this task.

Use native history and diff operations. For jj, read tracked files with
`jj file show -r <revision> <path>` and compare revisions with
`jj diff --git --from <base> --to <head>`. Read-only `git patch-id --stable`
plumbing may fingerprint that diff when a shipping verdict requires it.

Keep ordered, verifiable changes with native describe/new/split/rebase operations
when they belong to the task. Do not stage with Git in a jj repository.
Pausing a jj working copy does not require a WIP commit; preserve its change and
save the project's checkpoint. Never bundle another worker's edits to pause.

## PR handoff

Use the installed [Opening a PR](../playbooks/opening-a-pr.md) playbook and the
project's approved PR workflow with actual forge tools. Opening, commenting,
pushing, merging, and deploying require the applicable user authorization.
A verification request does not grant it.

If PR creation is not authorized, return the verified change, evidence, and
remaining handoff instead of opening one. Do not weaken shipping's independent
verdict, exact-patch, or bottom-up stack requirements. Missing verdicts or forge
capabilities stop the affected landing step.

## Native helpers

The helpers ship with `dav-mode`. Run them from the target repository or the
program's chosen state directory, not from the installed skill directory.

| Helper | Command | Boundary |
| --- | --- | --- |
| Workspace audit | `python3 ~/.agents/skills/dav-mode/scripts/workspace-audit.py -b main <repo-path>` | Read-only captured jj state; optional live tracked-byte comparison; never deletes or certifies safe cleanup. |
| Plan validator | `node ~/.agents/skills/dav-mode/scripts/check-plan.mjs <plan.md>` | Checks the plan skeleton and reports diagnostics. It does not verify its evidence. |
| Patch fingerprint | `node ~/.agents/skills/dav-mode/scripts/patch-id.mjs <base> <head>` | Requires jj. Prints a stable patch ID or `empty`. |
| PR watcher | `~/.agents/skills/dav-mode/scripts/watch-pr/watch-pr --pr <pr> --status-only` | GitHub only. Reads through authenticated `gh`. Without `--status-only`, polls until a terminal verdict. |
| Program store | `bun ~/.agents/skills/dav-mode/scripts/orch/orch.ts --help` | Stores unit, inbox, ledger, and status facts. Its frontier reads jj topology and GitHub PR identity, state, and head SHA. |

Node runs the plan and patch helpers. Bun runs the watcher and program store.
The Bun entry points install their locked dependencies on first use or a lockfile
change. The watcher and frontier require authenticated `gh` for GitHub reads.
The program store neither spawns agents nor schedules turns. A helper's output
does not grant authority or satisfy an independent-verdict gate.

## Skill authoring and cleanup

[Authoring a skill](../playbooks/authoring-a-skill.md) now maps the upstream
Cursor dependency to the installed [skill-creator](../../skill-creator/SKILL.md).
The user explicitly approved the complete public Anthropic workflow under
Apache-2.0, not a claim that Cursor's built-in source was recovered. Its native
Yuke/macOS helpers provide authorized bounded model trials, private stores,
sandboxed writes, retained histories and budgets. Full paired/human-review and
20-query repeated description campaigns remain separate execution gates.
Verification-skill generation keeps its specialized installed workflow.

[Workspace cleanup](../playbooks/worktree-cleanup.md) uses
`python3 ~/.agents/skills/dav-mode/scripts/workspace-audit.py -b main --check-live-files <repo-path>`.
The helper is read-only at a fixed jj operation. It never fetches, snapshots,
queries unrelated transcripts, or marks a workspace safe. Untracked/ignored
disk state, PR state, pinned sessions, and unsaved editor state remain separate
evidence gates. Forgetting a workspace leaves its directory; deleting that
directory, simulator state, or caches requires explicit approval.
