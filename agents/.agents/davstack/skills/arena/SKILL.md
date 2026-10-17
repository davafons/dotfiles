---
name: arena
description: "Spawn N parallel candidates at the same task, pick a base, graft the strongest parts of the losers into it. Use for /arena, 'arena this', 'throw it in the arena', or when one attempt at a non-trivial artifact would lock in the wrong shape."
disable-model-invocation: true
license: MIT
metadata:
  upstream: https://github.com/cursor/plugins/tree/1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def/pstack/skills/arena
  revision: 1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def
---

# Arena

## Runtime adaptation

Read the [shared working rules](../dav-mode/references/working-rules.md) and
[native coordination contract](../dav-mode/references/playbook-runtime.md#design-and-coordination).
They govern tools, model roles, workspace ownership, and authority throughout
this method. Preserve every phase and required output. Missing independent
workers, a judge, or safe output isolation leaves that gate open, not passed.
Installing this skill does not authorize delegation, model trials, or publication.

Open a todolist with one entry per phase (Frame, Fan out, Cross-judge, Pick, Graft, Verify) before launching anything.

## Phase A: Frame

Every candidate gets the same prompt, so the prompt is the contract.

1. State the artifact each candidate is producing.
2. Derive the rubric, 3-6 concrete gradeable criteria for what success looks like on *this* task. It is the picker's tool in Phase D. Candidates only see the task.
3. Pick the runners from the current harness's configured roles under the native coordination contract. Record intended and engine-accepted models. Honor actual role inheritance rather than passing unsupported model arguments. A missing required seat is a gap, not permission to add a provider or guess a fallback. Spawn more runners when the arena covers multiple design directions. Use the same model N times when the work is generation-bound rather than judgment-sensitive.
4. Give each candidate its own output location (an isolated jj workspace where possible, otherwise `/tmp/arena-<slug>/candidate-<n>/`), per the **separate-before-serializing-shared-state** principle skill.

## Phase B: Fan out

Dispatch all N authorized candidates through the supported native fan-out lifecycle, each with the task, the path to the shared grounding, its own output path, and instructions to produce the artifact and a short rationale naming the alternatives it considered and what it rejected. End the turn when the harness requires waiting. Do not claim parallel candidates when the dispatch cannot provide them.

If a candidate produces no output, proceed with N-1 and note the dropout.

## Phase C: Cross-judge

After all Phase B candidates complete, choose an available configured judge under the native coordination contract. Prefer a different model family from the parent's; if a caller requires one, an unavailable family blocks that gate. Spawn one fresh review-only judge session. It sees the rubric and the candidates by neutral path label without model identities, scores each criterion, and recommends a base with rationale. Its work can overlap your Phase D reading only when the harness permits that work after dispatch. Otherwise resume your reading when the report arrives. Do not spawn it while candidates are still writing.

## Phase D: Pick a base

Read every candidate end to end before picking. Score each against the rubric criterion by criterion, not on holistic feel, and compare with the cross-judge. Agreement on the base confirms the pick. Disagreement means one of you is biased or the rubric was ambiguous. Read both rationales before deciding.

Pick the base a future maintainer can extend most easily without breaking invariants. When two feel tied, prefer the cleaner boundary or smaller API, per the Laziness Protocol.

## Phase E: Graft

Walk each losing candidate once more for what is worth porting into the base, usually one or two things per candidate, not most of it. Fold each graft in by hand, per the **redesign-from-first-principles** principle skill, so the result stays coherent under one mental model. Don't paste mechanically.

If the candidates converge on one shape, that is strong agreement. Note it and ship the consensus shape. No graft is needed. If they wildly diverge, Phase A was under-specified. Reframe and re-run rather than averaging the divergence.

## Phase F: Verify

Verify the synthesized artifact like any other output, per the **prove-it-works** principle skill. If verification finds a problem the arena missed, either Phase A was wrong (re-frame and re-run) or a candidate caught it and you missed the graft (go back to Phase E). Don't paper over it.

## Outputs

One synthesized artifact, with a short synthesis note alongside naming the base and why, the cross-judge's verdict, each graft with its source candidate, what was rejected and why, any convergence or dropouts, and the verification result.
