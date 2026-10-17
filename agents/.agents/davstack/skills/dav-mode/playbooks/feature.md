# Feature

Read [Playbook runtime](../references/playbook-runtime.md) before executing these steps.

**You own the design. Plan, review, verify.** Delegate implementation. Stay in the lead.

1. `how` over the affected subsystem.
2. [architect protocol](../../architect/SKILL.md) for parallel design exploration.
3. Write the throughput checkpoint as four todo items. A dimension that genuinely does not apply (single file, no fan-out) keeps its item with `n/a: <reason>` rather than being dropped:
   - **Blocking first steps.** Gates run before fan-out.
   - **Independent workstreams.** Disjoint files, services, or layers parallelize. Shared writes serialize.
   - **Shared mutable state.** Default to splitting the target (the [separate-before-serializing-shared-state principle](https://github.com/cursor/plugins/blob/1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def/pstack/skills/principle-separate-before-serializing-shared-state/SKILL.md)). Serialize only for real invariants.
   - **Smallest safe decomposition.** If one worker is best, name why.
4. Delegate code-writing to a subagent using your configured feature model with a specific scope (file paths, named data shape and its organizing structure per [model-the-domain principle](https://github.com/cursor/plugins/blob/1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def/pstack/skills/principle-model-the-domain/SKILL.md), a state machine over scattered booleans, a table/registry over branching, a typed model over repeated shape assumptions, chosen before the delegate writes logic, and success criteria). When the implementation admits multiple valid shapes (error handling, abstraction layer, test structure), delegate via the [arena protocol](../../arena/SKILL.md) instead so the runners surface the alternatives and the cross-judge guards the pick. Review separation is required, not a lines-saved optimization. Apply the runtime delegation rules. If independent review cannot run, keep that gate open rather than treating self-review as equivalent. A delegate forbidden to spawn owns its diff directly and returns it to its parent for review. No "standing by" reply that waits on a nested agent. Comments per [the canonical comment review rules](../../comment-sicko/SKILL.md). Surgical edits, re-ground against the source for upstream-derived files. Port shared-primitive improvements to all consumers and verify each. Keep scoped, verifiable changes through the repository's native version-control workflow.
5. Verify on the matching surface. "Inconclusive" or wrong-surface is not a pass. Flag it.
6. Rebase into small, ordered commits. Stack follow-ups.
   Use the [sequence-verifiable-units principle](https://github.com/cursor/plugins/blob/1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def/pstack/skills/principle-sequence-verifiable-units/SKILL.md), building, verifying, and committing each small unit before the next.
7. If the design is contested, [interrogate protocol](../../interrogate/SKILL.md) before shipping.
8. Complete the [PR handoff](../references/playbook-runtime.md#pr-handoff).

Code-coupled work (one feature, one migration) goes to a single owner with the checkpoint inline. That owner fans out internally after the blocking phase. Parent-level fan-out is for slices that produce independent artifacts (audits, cross-subsystem investigations, competing experiments). Rewrite the checkpoint at phase boundaries. Spawn a fresh owner rather than chaining interrupts.

**Reply:** what you built, what you chose and why, the throughput checkpoint, open decisions. Tables for design alternatives.
