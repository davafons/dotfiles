---
name: reflect
description: Apply judgment, tooling, and divergent review lenses to the active transcript, synthesize Accepted / Rejected / Backlog findings, and propose edits to existing skills. Use when the user says reflect. Delegation requires explicit permission.
disable-model-invocation: true
license: MIT
metadata:
  upstream: https://github.com/cursor/plugins/tree/1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def/pstack/skills/reflect
  revision: 1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def
  origin: shirabe
  origin-path: docs/agents/reflect.md
  origin-revision: 968e24d69837e3efecca31487f7d8e8508e803c8
---

# Reflect

## Runtime adaptation

Read the [shared working rules](../dav-mode/references/working-rules.md) and
[playbook runtime](../dav-mode/references/playbook-runtime.md).
Keep reviewer and synthesizer evidence lookups read-only and within this session's
scope. Use jj for history and `jj diff --git` for patches. Do not query unrelated
chats, credentials, or active user sessions.

Delegation requires explicit permission. Use the native child API, configured
reviewer roles, and actual start-and-wait lifecycle. Inherit configured defaults
when no role is configured. Do not assume Cursor Task fields, per-call model
selection, or that a read-only flag controls MCP access in this runtime.
Without delegation permission, apply all three templates serially yourself,
then synthesize. Label this as direct review, not independent or cross-model proof.

The `create-skill` routing labels below name an upstream authoring workflow, not
an installed command. Resolve a supported native skill-authoring workflow before
executing those rows. If none is available, keep that routing open and report the
gap. Do not replace its draft / test / iterate or description-optimization loop
with an ad hoc edit. Creating a verification skill is a different workflow.

Mine the current conversation for durable learnings, then route them into skill edits.

Invoke when the user says "reflect" or "/reflect". Skip when the conversation is trivial, off-topic, or already covered by an existing skill the parent followed correctly. One-offs are not learnings.

## 1. Locate the active transcript

Before fanning out, obtain only this conversation's transcript through the
current harness's authorized history API or export. Use the session identifier
supplied by the runtime. Do not assume Cursor's `agent-transcripts/` paths or
search other workspaces. Verify the export against the opening user prompt.
If no matching export is available, pass a tight digest of the current session
instead. Label the digest's limits and retain actual turn references or quotes.

## 2. Spawn three reviewers in parallel

When delegation is authorized, spawn three native reviewers in parallel.
Reviewers may use the available read-only evidence APIs to look up only the
tickets, chat threads, and traces this transcript references. Pass shared-desktop
restrictions and return findings through the native child report.

Use the configured role for each lens. Missing independent roles or model
families remain explicit capability gaps. Without delegation permission, perform
these three review passes serially with the same templates.

| Lens | Configured role | Prompt template |
|---|---|---|
| Judgment | Judgment reviewer | `references/judgment-reviewer.md` |
| Tooling | Tooling reviewer | `references/tooling-reviewer.md` |
| Divergent | Divergent reviewer | `references/divergent-reviewer.md` |

Pass each template verbatim, substituting the transcript path or digest where marked. Reviewers return findings through the native child report, or the direct review record.

## 3. Synthesize

After all three review passes complete, run one synthesizer with
`references/synthesizer.md` verbatim and each reviewer's full output inlined where
marked. Use the configured synthesizer role through the native child API when
delegation is authorized, or synthesize directly otherwise. Spot-verify citations
through available read-only evidence tools. It returns an Accepted / Rejected /
Backlog list. A direct synthesis is not an independent judgment.

## 4. Structural enforcement check

Move any Accepted item that a lint rule, script, metadata flag, or runtime check would enforce more reliably to Backlog. See the [encode-lessons-in-structure principle](https://github.com/cursor/plugins/blob/1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def/pstack/skills/principle-encode-lessons-in-structure/SKILL.md).

## 5. Apply

Present the synthesizer's full Accepted / Rejected / Backlog output and wait for explicit approval before applying any Accepted edit. The user picks the subset and may redirect routings. Skill changes affect every future agent in the org. Do not auto-apply.

File each Backlog item in the project's internal task record with `project_work`. This does not authorize external tracker writes. Only the Accepted list waits for approval. Use the team's external tracker only with applicable authorization.

Follow each approved row's Routing exactly:

- Trivial existing-skill edit (a one-line bullet, a tightened sentence, a stale fact corrected): the parent does it directly.
- Substantive existing-skill edit (a new section, a new pattern table, more than ~10 lines): hand to the supported skill-authoring workflow and run its draft / test / iterate loop. If none is available, report the routing as blocked.
- `tune description: <skill path>` (the skill exists but didn't trigger when it should have): hand to the supported skill-authoring workflow and run its description-optimization loop. If none is available, report the routing as blocked.
- `new skill via create-skill: <kebab-name>`: hand creation to the supported skill-authoring workflow. If none is available, report the routing as blocked. Do not invent the shape ad hoc.

If your environment ships an authorized SKILL.md validator, run it on every touched skill before declaring done. Respect the project's exclusions on skill-prose, metadata, and reference-structure tests. A missing or excluded validator is a reported gap, not a passed check.

## 6. Summarize for the user

Short list, no preamble:

- Edits applied: `<skill path>`. What changed, one line each.
- New skills created: `<skill path>`. One line each (rare).
- Backlog filed to the internal task record or authorized devex tracker: `<issue title>` (`<tags>`). One line each.
- Dropped: one line per rejected finding + reason from the synthesizer.
