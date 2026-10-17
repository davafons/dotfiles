# Bug fix

Read [Playbook runtime](../references/playbook-runtime.md) before executing these steps.

Select each delegate's reasoning level and speed per [dav-mode's Subagents rules](../SKILL.md#subagents), using only controls the current harness actually supports.

**You own this task. Plan, review, verify.** Delegate investigation and the fix to subagents, stay in the lead.

Be scientific. Every shipped line traces to runtime evidence. Belt-and-suspenders that "might help" is a hypothesis, not a fix. It does not ship. When evidence refutes a hypothesis, revert what it motivated. The smallest change the evidence justifies ships, nothing more.

1. Reproduce it yourself on the matching surface through the project's matching verification/control workflow, even when a debug or instrumentation protocol says to ask the user to reproduce. Ask the user only with a stated, specific reason the control surface cannot reach the target, and only after driving it as far as it goes. If it won't reproduce directly, synthesize the trigger, tighten conditions, or instrument until it fires.
2. Binary-search the cause. Form the candidate hypotheses, then rule them out until one survives. Seed them with `how` over the affected subsystem and the **why** skill for regression history. Each pass, take the split that cuts the most remaining problem space, get runtime evidence, eliminate. When program state is unclear, add instrumentation or logging and read it as the code runs. Don't guess. Drive a long or stubborn hunt with an explicit hypothesis/instrumentation loop through the current harness. Confirm the surviving *mechanism* with runtime evidence before the step-3 design and adversarial-review fan-out.
3. Plan the fix. If it crosses a function boundary, [architect protocol](../../architect/SKILL.md) first. Delegate implementation to a subagent using your configured bug-fix model with a specific scope.
4. Verify on the same surface. The original repro now passes. "Inconclusive" or wrong-surface is not a pass. Flag it. Unit tests show branch behavior, not bug absence.
5. Order the changes so the failing repro lands before the fix in version-control history. Use the repository's native change operations; do not stage with Git in a jj checkout. See the **tdd** skill for the failing-test-first cadence when the bug has a cheap local test path. Skip it when the test would be expensive, integration-heavy, or unclear.
   This is the canonical [sequence-verifiable-units principle](../../principle-sequence-verifiable-units/SKILL.md), the failing test first and the fix on top.
6. Complete the [PR handoff](../references/playbook-runtime.md#pr-handoff).

**Reply:** what was broken, root cause, fix, how you verified. Paste failing-then-passing repro output verbatim.
