---
name: reflect
description: 'Mines this session for durable lessons and routes each one to the strongest place it can live: a test, a lint, a runtime check, a canonical helper, a doc, or AGENTS.md. Proposes every change and waits for approval before applying any. Use at the end of a substantial session, after a hard-won fix, or when the user says "reflect".'
metadata:
  origin: shirabe
  origin-path: docs/agents/reflect.md
  origin-revision: 968e24d69837e3efecca31487f7d8e8508e803c8
---

Read the [shared working rules](../dav-mode/references/working-rules.md) before applying this skill.
Project instructions supply the commands and conventions; examples are not prerequisites.

# /reflect

The feedback loop. Without it a lesson from a session lands only if somebody remembers to
write it down, which is the same weakness as every other instruction: it depends on memory.

## When this is worth running

- A task took real work and produced a reusable recipe.
- You went down dead ends and found a path worth not rediscovering.
- The user corrected your approach mid-task.
- A fix revealed something structural: a whole class of bug, a wrong assumption in a doc, a
  guard that does not exist.

Skip it for trivial or off-topic sessions, and skip anything already covered. Adding a rule
that is already written is worse than adding nothing: it splits the rule across two homes.

## 1. Mine the session

Go back over the transcript and pull out what is durable, separating three things:

- **What was learned about the system** (a real invariant, a measured dead end, a defect class).
- **What was learned about how to work here** (a command that failed and the one that worked, a
  trap in the tooling, a repeated correction).
- **What went wrong in your own approach**, including anything the user had to say twice.

Be specific. "Be more careful with sweeps" is not a lesson. "A mechanical dash sweep rewrote a
regex character class and a test's input string, so a sweep over prose must exclude anything
inside a literal" is.

## 2. Route each one to the strongest rung

This is the whole point. For every lesson, pick the strongest place it can live and say why
the stronger ones do not apply. The ladder is in the [shared working rules](../dav-mode/references/working-rules.md):

A lesson that lands on rung 5 needs a reason it could not land higher. "It is judgment" is a
real reason. "It would take longer" is not.

Then pick the file using the project's document layout. A feature fact goes to its
permanent feature owner, a system fact to architecture, a local working rule to
conventions, and only a rule that shapes every action goes to AGENTS.md, which every
session pays for. A reusable personal workflow belongs in davstack, not a project copy. A rule bound to one activity is a
skill, not a line in AGENTS.md.

## 3. Propose, then stop

Present the full list before touching anything: the lesson, the rung, the target file, and the
exact change. **Wait for explicit approval.** The user rejects freely and you do not argue for
a rejected item twice.

Rejections are worth as much as acceptances. Say plainly which ones you dropped, so the same
proposal does not come back next session.

## 4. Apply what was accepted

Build each accepted item at the rung it was assigned. A rung-2 item means a script or a check
exists in the diff: **if you cannot point at one, you did not do it.** Prove a new test by
watching it fail without its fix. Run the project's house/style checks and the narrowest relevant suite.

Then report what landed, what was declined, and anything left open.
