# Playbook runtime

Read the [shared working rules](working-rules.md). User and runtime instructions
outrank a playbook. Keep its method and verification gates; adapt its tools,
not its purpose. A missing capability is a reported gap, not a passing result.

## Source

The 14 selected playbooks are adapted from
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

Links to upstream `architect`, `arena`, `swarm`, `interrogate`,
`benchmark-checklist`, `show-me-your-work`, and `principle-*` files are protocol
references, not installed skills. Read the relevant source when its method is
required. Apply that method through available tools and the shared rules.
Do not invent an invocation, silently install a dependency, or claim that reading
its instructions executed it.

Preserve the method's required outputs: distinct design candidates and synthesis,
blinded judging, lane coverage, measurement vetting, and decision evidence.
Report unavailable automation or independent roles. Keep required gates open
when they cannot be satisfied; do not weaken them to match the available tools.

For document writing, use [the installed writing reference](../../technical-writing/SKILL.md)
and [unslop](../../unslop/SKILL.md). Follow the project's plan and evidence locations.
Upstream execution protocols linked by a plan are not locally installed playbooks.
Name a supported execution workflow and its gaps before asking to start it.

## Control surfaces and loops

Use the project's verification/control skill or a proven CLI, API, or browser
workflow for the matching surface. Do not substitute a unit test for the original
live reproduction. Apply desktop permissions before instrumentation or GUI work.
A live hotfix also needs applicable authority; diagnosis does not authorize
production mutation.

Use only an available, authorized scheduler for recurring ticks. A foreground
iteration is not a persistent background schedule. If no scheduler can survive
the session, report that gap and do not claim the cadence is armed. Save a
checkpoint at the safe boundary instead.

Read only the named session's history through an authorized current-harness API
or export. Never assume another editor's transcript paths or search unrelated chats.

## Version control and durable state

Check for `.jj/` before version-control commands. In colocated repositories use
`jj`; use Git only where no `.jj/` exists. Follow project branch and push rules.
A shared working copy must not be described, split, or rebased as if all its
changes belonged to this task.

Use native history and diff operations. For jj, read tracked files with
`jj file show -r <revision> <path>` and compare revisions with
`jj diff --git --from <base> --to <head>`. Read-only `git patch-id --stable`
plumbing may fingerprint that diff when a shipping verdict requires it.

Keep ordered, verifiable changes with native describe/new/split/rebase operations
when they belong to the task. Do not stage with Git in a jj repository.
Pausing a jj working copy does not require a WIP commit; preserve its change and
save the project's checkpoint. Use a scoped WIP commit in a Git-only repository
when needed. Never bundle another worker's edits to pause.

## PR handoff

The upstream [Opening a PR protocol](https://github.com/cursor/plugins/blob/1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def/pstack/skills/poteto-mode/playbooks/opening-a-pr.md)
is not an installed local playbook. Use the project's approved PR workflow and
actual forge tools. Review its required preparation before a PR-facing handoff.
Opening, commenting, pushing, merging, and deploying require the applicable user
authorization. A verification request does not grant it.

If PR creation is not authorized, return the verified change, evidence, and
remaining handoff instead of opening one. Do not weaken shipping's independent
verdict, exact-patch, or bottom-up stack requirements. Missing verdicts or forge
capabilities stop the affected landing step.
