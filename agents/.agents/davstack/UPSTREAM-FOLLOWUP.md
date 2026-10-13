# Upstream fidelity and runtime verification

This report covers the five-step follow-up on 2026-10-13. Source comparisons use
[cursor/plugins at `1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def`](https://github.com/cursor/plugins/tree/1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def/pstack/skills).
The earlier `how` import at `d73344bee8cf22e53b9d5f4cf5749d38ba38c174` remains
part of its recorded lineage, not the current method baseline.

At the time of this follow-up, the installed set had 16 development skills and
20 playbooks. The subsequent approved adoption added `benchmark-checklist`,
`show-me-your-work`, and `trace-forensics`, bringing the set to 18 skills and
21 playbooks. The decisions below record the earlier assessment. This pass
restores existing skills and assesses dependencies. It does not import the
remaining protocol catalogue.

## Restored methods

| Area | Previous local difference | Current method | Runtime adaptations |
| --- | --- | --- | --- |
| `how` | A shortened four-step checklist replaced upstream routing. | Simple questions use one explainer pass. Complex questions use 2 to 4 distinct exploration angles, then one synthesis with all findings. Presentation keeps the explainer's output. | Native child API and configured roles, explicit delegation permission, a declared direct serial path when delegation is unavailable, read-only investigation, and jj history. |
| `reflect` | A different local workflow replaced upstream review and synthesis. All four supporting templates were absent. | Judgment, tooling, and divergent review lenses feed the full synthesizer template. Findings become Accepted, Rejected, or Backlog. Structural enforcement moves to Backlog. Accepted edits wait for approval. | Current-session history API or a labeled digest, native child lifecycle, read-only evidence lookups, internal task records, and jj. Unsupported skill-authoring routes remain open. |

The upstream `reflect` reviewer and synthesizer templates retain their finding
criteria, injection defenses, evidence requirements, and output formats.
Cursor-only skill paths and tool names now refer to actual file reads, scoped
briefs, and available read-only evidence tools.

Reflection restores skill-edit proposals, not automatic edits to project docs or
AGENTS.md. Findings better enforced by code, a lint, or a runtime guard belong in
the internal backlog. Proposing a skill edit does not approve it.

## Native discovery evidence

The optional driver is
[`bin/tests/check_agent_discovery.py`](../../../bin/tests/check_agent_discovery.py).
It runs native CLI control protocols in private temporary homes. It sends no
user model turns, uses no real provider credentials, starts no delegates, and
never attaches to an active user session.

| Runtime | Observed result | Not proven |
| --- | --- | --- |
| Claude Code 2.1.296 | Native initialization lists `comment-sicko` and `dav-agent` from the isolated user-agent directory. Bare mode omits them. | Agent execution, canonical skill reads during execution, effective tool enforcement, and independent model behavior. |
| Codex CLI 0.162.1 | Native config read and an ephemeral empty thread work with an offline provider. The thread is read-only with network access disabled. | These diagnostics do not expose the custom-agent catalog. Discovery, spawning, instruction resolution, and effective child overrides remain unverified. |

The [Codex subagent documentation](https://developers.openai.com/codex/agent-configuration/subagents)
describes standalone files under `~/.codex/agents/`. That supports the adapter's
installation shape, but documentation is not an observed catalog result.

Claude's bare mode is not a directory-discovery check. Its explicit-context
contract differs from normal user-agent loading. The driver distinguishes the
modes instead of treating the absent bare-mode entries as a broken installation.

## Model evaluation status

The operator selected a local, model-free run. No candidate or independent judge
was started. The [Eval playbook](skills/dav-mode/playbooks/eval.md) requires real
candidate outputs, blinded judgment, and transcript evidence. Its gates remain
open. Installer checks, native startup diagnostics, and helper tests do not
replace that evaluation.

The existing helper suite passes 71 behavioral tests and strict TypeScript
checking. It exercises plan validation, jj frontier safety, stale or omitted
members, forge refusal, and stable patch fingerprints. These are helper results,
not evidence that a model follows a workflow.

## Remaining protocol assessment

The following main files and their supporting references were read at the same
pinned revision. At that assessment each remained a protocol reference. The
subsequent approved adoption installed `benchmark-checklist` and
`show-me-your-work`; the other four remain references.

| Protocol | Useful contract | Required native adaptation | Decision |
| --- | --- | --- | --- |
| `architect` | Ground the system, produce at least two structurally distinct usage-first sketches, screen red flags, synthesize, implement, and scrap a wrong shape. | Native role configuration, isolated jj workspaces, authorized candidates, and the complete runner, red-flag, and rationale templates. | Keep the reference. Import only with an actual design task and a supported candidate-and-synthesis path. |
| `arena` | Shared organic task, private rubric, independent outputs, cross-judge, base selection, grafting, and final verification. | Native model seats and child lifecycle, jj workspaces, and real independent judging. | Keep the reference. A serial self-review is not a replacement. No model-backed run was authorized here. |
| `swarm` | Coverage or race rules declared before launch, exact revisions and measurement method in each brief, terminal evidence, and explicit missing slices. | Native child API and available environments instead of Cursor cloud fields. Each writer needs an owned jj workspace or output directory. | Keep the reference. The current API's start-and-wait contract must govern execution, not an invented cloud or background field. |
| `interrogate` | Same intent and rubric for diverse reviewers, evidence-backed findings, synthesis, and pragmatic Act on / Consider / Noted / Dismissed judgment. | `jj diff --git` against the owned base, native reviewer seats, read-only briefs, and available model families. | Keep the reference. Import is useful only when independent diverse reviewers can actually run. |
| `benchmark-checklist` | Explain the limiter, production tuning, physical limits, errors, repeatability, relevance, and whether the timed work happened. | macOS diagnostics such as `sysctl -n hw.logicalcpu` and supported profilers instead of assuming `nproc`, `pidstat`, or `perf`. | A low-dependency candidate for a later explicit import. No benchmark or speed claim was made here. |
| `show-me-your-work` | One append-only decision log with evidence pointers, transcript audit, and independent cross-model review before handoff. | A state directory outside jj snapshots, current-harness transcript access, and an authorized independent reviewer. | A low-dependency candidate for a later explicit import. Its logger ran on macOS and preserved append behavior, cell boundaries, and formula escaping. Cross-model review remains a separate gate. |

The principle catalogue remains pinned source material. Its relevant leaves are
read when a task needs them. No new principle skills, model-role registry,
scheduler implementation, or generic skill-authoring substitute was installed.

## Verification and artifacts

The source and adaptation record lives at:

```text
~/.cache/davstack/reviews/fidelity-next-five/1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def/
```

It contains the pinned originals, pre-change source copies, adaptation patches,
native discovery receipts, and the logger portability result. The native driver
prints its private artifact directory on each run.

Repository checks pass 31 behavioral tests plus ShellCheck. The installed-link
check passes. No tests assert skill prose, metadata, or reference structure.
No user session was reloaded, no schedule was armed, and no push or merge was
performed. Independent model evaluation and active-agent execution were not run.
