---
name: tdd
description: Make a bug executable before changing production code. Use when fixing a bug with a cheap local test path, or when a failing test or regression test is asked for. Skip when the test path is unclear, expensive, or integration-heavy.
metadata:
  origin: shirabe
  origin-path: docs/agents/tdd.md
  origin-revision: 968e24d69837e3efecca31487f7d8e8508e803c8
---

Read the [shared working rules](../dav-mode/references/working-rules.md) before applying this skill.
Project instructions supply the commands and conventions; examples are not prerequisites.

# TDD bug fix

When fixing a bug with a clear, cheap test path, make the broken behaviour
executable before changing production code. The goal is a focused regression
test that fails before the fix and passes after it.

Do not force a test where it would be impractical: broad harness setup, brittle
mocks, production-only state, vague reproduction steps, or large unrelated
fixture churn. Use the closest useful verification instead, and say why.

## Workflow

1. **Understand the bug.** Intended behaviour, current behaviour, the affected
   path, and the smallest observable reproduction.
2. **Choose the narrowest executable check.** Prefer the test file that already
   covers that codepath. If no practical path is obvious, do not invent one to
   satisfy the workflow.
3. **Write the failing test first.** The smallest test that would have caught
   the bug. It encodes intended behaviour, never the current implementation.
4. **Run it before fixing, and watch it fail for the intended reason.** If it
   passes, or fails for an unrelated reason, the test or the reproduction is
   wrong. Fix that before touching the implementation.
5. **Fix the bug.** The smallest production change that satisfies the intended
   behaviour while preserving nearby contracts.
6. **Rerun it.** Confirm it passes.
7. **Run nearby validation.** Adjacent tests, the ratchets guarding what you
   touched, and the project's linters when the change has wider reach.

## When a failing test is impractical

Do not silently skip the regression step. Say why it is impossible or not worth
the cost, then pick the closest executable check: a targeted script, a project
task, a reproduction command, a log assertion, a focused integration check.

**Prefer no new test over a bad test.** A bad test is one that mostly tests
mocks, encodes implementation details, depends on timing or global state, needs
expensive infrastructure for a small fix, or would be deleted the moment it has
proved the fix.

## Guardrails

- Do not change a test to match a wrong implementation.
- Do not weaken an existing assertion unless the expected behaviour genuinely
  changed and the reason is clear.
- Keep the test focused on the bug. No unrelated coverage expansion.
- If the bug is flaky, make the test deterministic and say what signal is being
  locked down.
- If the bug exposes a whole class, land the focused regression first, then ask
  whether a lever catches the rest (the shared working rules, "Where a rule lives").

## Report

The evidence, not the outcome:

- The failing-before test and **the failure it produced**.
- The passing-after run, and any nearby validation.
- If failing-before could not be shown, why, and what was used instead.
