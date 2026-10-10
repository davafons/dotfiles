---
name: figure-it-out
description: 'Design an auditable playbook when no narrower one fits: a large migration, an ambitious multi-part change, or work the user reviews after stepping away. Scales rigor to the task, runs a hypothesis loop, and leaves a trail. Use for "figure it out", or when no playbook in dav-mode matches.'
metadata:
  origin: shirabe
  origin-path: docs/agents/figure-it-out.md
  origin-revision: 968e24d69837e3efecca31487f7d8e8508e803c8
---

Read the [shared working rules](../dav-mode/references/working-rules.md) before applying this skill.
Project instructions supply the commands and conventions; examples are not prerequisites.

# Figure it out

When the task matches no playbook, design one. The deliverable before any code
is the workflow itself: phases that scale rigor to the task, run the scientific
method, and leave a trail someone can audit after stepping away.

Bias toward more rigor. The cost of building the wrong thing dwarfs the cost of
being careful.

**Do not reinvent a playbook you already have.** A focused single-unit task that
matches Investigate, Bug fix, Prototype, Feature, Refactor, Write, Encode, Plan
or Ship routes to that [playbook](../dav-mode/SKILL.md). A large or cross-cutting version of
one belongs here even though the single-unit version would be a Feature. The
rigor and the trail are the point.

## Phase A: Frame

Ground first, then commit. Do not start the run until you can state:

- **Done, as a falsifiable predicate.** "Done well" has to be checkable. A
  command, a number, a test that fails today.
- **Scope, quantified.** Rough units and effort, plus the blockers grounding
  surfaced. Raise them before spending hours, not after fifty doomed commits.
- **The rigor level, biased high.** Anything irreversible earns more; reversible
  low-stakes steps earn less. Rigor is gates and artifacts, not trying harder.

Reversible work proceeds without asking (the shared working rules), but a
multi-hour run earns one checkpoint. Present the framing and the tradeoffs.

## Phase B: Design the workflow

Decompose into atomic, independently-landable units. Sequence
riskiest-unknown-first, so option value stays high. Scaffold and verification
come before features.

- **Build the check before the work**, with the baseline captured from the
  pre-change state, so the result reads as "old value against new value" rather
  than as an assertion. An eval ratchet is the strongest form of this here.
- **For a decision that is hard to walk back**, write the alternatives down and
  say what would settle each, before writing the code that assumes one. A
  measured dead end is worth more than a second design pass over a settled one.
- **Decide what can fan out.** Delegation requires an explicit user request.
  Use the checkout's actual ownership boundary. In a shared checkout the seam
  is files; inspect current state before a sweep or history change, and preserve
  others' work. Do not restructure their changes to isolate yourself.
- **Write the phase list down.** That list is what the user reviews.

Then put the design into motion: add its steps to the todo list as concrete
items, and run each under the Phase C loop.

## Phase C: Run the loop

Each unit is an experiment. State the hypothesis, make the smallest change,
measure against the predicate **on the real artifact**, keep it if it advanced,
revert it if it did not. Verify each unit before starting the next, rather than
batching the checks at the end.

- **Inspect the artifact, never a self-report.** When something passes too
  easily, suspect the observation method before the system.
- **A verdict is VERIFIED, NOT VERIFIED, or INCONCLUSIVE.** Inconclusive is not
  a pass. Do not hide a negative.
- If a gate is wrong, fix the gate in its own change rather than routing around
  it.

## Phase D: Keep the trail

Use the project's existing plan or checkpoint format. Record what is true now,
what happens next, and real blockers. Overwrite the snapshot as the run moves;
do not append a diary. One owner per plan. Use its freshness check if available.

Prefer evidence produced by a committed script, so the next reader can rerun it
rather than trust the write-up. Promote every durable fact to its permanent
owner and delete the plan when the run ends. Version control is the archive.

## Phase E: Verify and hand back

Check the whole against the Phase A predicate on the real product, not just on
the harness. Then encode any correction you made twice as a check that fails
(the shared working rules, "Where a rule lives"), so the win cannot silently regress.

**Reply:** the playbook you designed, the rigor level and why, where the trail
is, what is verified against the predicate, and what is still open.
