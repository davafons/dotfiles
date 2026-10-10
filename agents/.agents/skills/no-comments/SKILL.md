---
name: no-comments
description: Removes comments from a file, directory, or diff. Runs the comment-sicko review, rejects its bad calls, applies the accepted deletions, fixes the code that needed explaining, and offers to encode any real constraint as a test or lint. Use when asked to clean up, reduce, or review comments.
metadata:
  origin: shirabe
  origin-path: docs/agents/no-comments.md
  origin-revision: 968e24d69837e3efecca31487f7d8e8508e803c8
---

Read the [shared working rules](../dav-mode/references/working-rules.md) before applying this skill.
Project instructions supply the commands and conventions; examples are not prerequisites.

# /no-comments

A comment is a cost on every future reader and nothing can test it. This removes the ones that
do not earn their place, and fixes the code whose unclarity produced them.

**Scope**: the files the caller named. With none given, the current diff against `main`,
working copy included. Inspect the actual diff using the repository's version-control tool.

## 1. Run the sicko

Read [comment-sicko](../comment-sicko/SKILL.md) and run its report-only review
on the scope. Delegate only if the user explicitly requested delegation or
parallel work. Otherwise run that lens serially yourself, then verify the
findings; do not call it an independent review.

When delegation is authorised, use the configured report-only agent if the
harness supports it. Do not restate its rules. If it cannot see its definition,
provide the canonical skill verbatim rather than summarising.

A large scope can be partitioned by directory, with a finding cap for each
report. Preserve file ownership in a shared checkout.

## 2. Reject its bad calls

The report is a proposal, not a verdict. **Verify before you apply.** On a prior sweep of this
repo one agent reported a method as untested that had a whole test file; the grep it claimed to
have run would have shown it.

Reject, and say why:

- Edits to application code that were not asked for, or anything outside the scope.
- A `MUST KILL` whose stated reason misreads the code.
- A flag on code that is intentional and correct.
- A deletion of a suppression without the exact exception that makes it safe.
- Removal of a load-bearing constraint before it is encoded or disproved.

Do not restore a comment just because a kill was aggressive. A `KEEP` must fit
one of comment-sicko's five categories; check each one yourself. For category 2,
require proof it is about something we cannot change. Retain an unencoded
load-bearing constraint until verified; otherwise ambiguity is not a reason to
restore a doomed comment.

Before accepting a thin `IMPORTANT` or `do not remove` either way, read the surrounding code
and the line's history (using the repository's version-control tool).

If a report is bad enough to reject wholesale, say what failed and rerun it once. Reject a
second and stop: report the scope as unswept rather than applying a report you do not trust.

## 3. Apply the deletions

Apply the accepted line ranges yourself, in one pass, bottom-up per file so earlier ranges do
not shift later ones. The agent never edits: this checkout is shared.

Then run the narrowest suite that covers the touched files. Ordinary prose
comments do not affect behaviour, but directives, pragmas, and generated-code
annotations can. Verify those before deletion. Also run the project's
house/style checks and the affected linter on any file where a suppression was
removed. Retain a load-bearing constraint until it is encoded or disproved.

## 4. Fix what needed explaining

Work the `MUST KILL` list. **"Implement the smallest root-cause fix in scope. Remove every
named workaround."** Rename the method, extract the branch, delete the dead path, give the
value a type, use the real API instead of the workaround the comment apologised for.

Where the fix is out of scope, land the smallest in-scope part and report the rest as open.
Never bolt on a guard to make a symptom go away.

## 5. Offer encodings, then wait

For each `TEST` finding, and for every genuine constraint a deleted comment carried, offer the
cheapest mechanism that can fail:

1. A DB constraint or an API that makes the bad state unrepresentable.
2. A lint that fails CI.
3. One canonical helper both callers use.
4. A runtime check that refuses.

**Wait for approval before writing any of them.** Encoding a constraint nobody asked for is
how a sweep turns into a refactor. Prove any test you do write by watching it fail without the
fix. Check the real test configuration; a cache-key test against a null store can
pass vacuously.

## 6. Report

Lines deleted, per file. `MUST KILL` fixes landed and left open. Encodings offered, accepted,
and declined. Comments restored, and why. Reports rerun. Anything you left unswept.

Give the honest total. A sweep that deletes 4 lines is a result too, and it means the comments
were earning their place.
