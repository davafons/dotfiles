---
name: dav-mode
description: The working mode. Names the playbook it matched, commits to its steps before starting, and carries the rules that hold whatever the task is. Read it at the start of any multi-step task.
metadata:
  origin: shirabe
  origin-path: docs/agents/dav-mode.md
  origin-revision: 968e24d69837e3efecca31487f7d8e8508e803c8
---

Read the [shared working rules](references/working-rules.md) before applying this skill.
Project instructions supply the commands and conventions; examples are not prerequisites.

# dav-mode

The stack, after pstack's `/poteto-mode`. Everything here is portable: the rules
below hold in any repo, the playbooks in `playbooks/` are shapes rather than
steps, and anything specific to this project lives in `AGENTS.md` instead.

**Read this at the start of any multi-step task**, and stay in it until the user
opts out ("not this time", "casual turn").

## How to use a playbook

1. Classify the task against the table and **say which playbook you matched**,
   in one line, before doing anything else.
2. Open that file and copy its steps into your todo list **verbatim, before any
   task-specific reasoning**.
3. A step you skip stays in the list with a one-line reason. Silent omission is
   the one thing this protocol forbids.
4. No match: say so. A small task you design out loud before starting; a large
   or cross-cutting one goes to **`/figure-it-out`**.

## The playbooks

**A lint checks the artifact. It cannot check the order you produced it in.**
That is what these carry: a test written after the fix and one watched failing
before it leave **identical** files, and a defect diagnosed before it was
reproduced looks exactly like one that was.

`/no-comments`, `/blast-radius`, `/reflect`, `/tdd` and `/unslop` are not listed:
each carries its own trigger and fires on its own.

| The task in front of you                               | Playbook                                      |
| ------------------------------------------------------ | --------------------------------------------- |
| A question answered by reading, changing nothing       | [Investigate](playbooks/investigate.md)       |
| A reported defect that needs reproducing first         | [Bug fix](playbooks/bug-fix.md)               |
| Measured slowness, or a number to move                 | [Perf](playbooks/perf.md)                     |
| One number, driven against a target over many tries    | [Hillclimb](playbooks/hillclimb.md)           |
| A live symptom to diagnose from instrumentation        | [Forensics](playbooks/forensics.md)           |
| A design or empirical fork you were about to ask about | [Prototype](playbooks/prototype.md)           |
| New or changed behaviour                               | [Feature](playbooks/feature.md)               |
| Behaviour-preserving restructuring                     | [Refactor](playbooks/refactor.md)             |
| Docs to write or restructure                           | [Write](playbooks/write.md)                   |
| Pixel-exact equivalence between two surfaces           | [Visual parity](playbooks/visual-parity.md)   |
| Measuring whether a prompt change changed behaviour    | [Agent eval](playbooks/agent-eval.md)         |
| A rule that keeps being restated or re-broken          | [Encode](playbooks/encode.md)                 |
| Work spanning sessions or agents                       | [Plan](playbooks/plan.md)                     |
| Taking over what another agent started                 | [Session pickup](playbooks/session-pickup.md) |
| Stopping cleanly, or context about to compact          | [Pause safely](playbooks/pause-safely.md)     |
| Shipping                                               | [Ship](playbooks/ship.md)                     |
| Nothing above fits, and the task is large              | **`/figure-it-out`**                          |

## Working rules

The [shared working rules](references/working-rules.md) hold whichever playbook
matched. They also apply when using one of the other davstack skills directly.

## Comments

Read [comment-sicko](../comment-sicko/SKILL.md) for the five allowed categories
and the report-only review. Use [no-comments](../no-comments/SKILL.md) to verify
its findings and apply cuts. The rules have one owner, not a second copy here.

Write them clean as you go. A ban applied afterwards does not catch them;
you have to not write the comment in the first place. A script narrating its
own phases does not need a comment above each block. The assertion or log line
is the documentation it needs.

## What we did not take from pstack

We did not import the `principle-*` catalogue. Prefer a test, lint, helper, or
runtime guard to another rule an agent has to remember. The selected upstream
skills and the migrated personal skills are catalogued in `DAVSTACK.md`.
