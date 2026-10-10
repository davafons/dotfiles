# Writing

The writing standard, adapted from pstack's `technical-writing`. The goal it sets is the whole
standard: **writing a tired engineer understands on the first read.**

## The four modes

Every document is exactly one of these. The names settle arguments.

**Tutorial** (action + learning). Learning by doing. You are the teacher and the
learner's success is your job, not theirs. Open with what they will have built.
Every step shows a visible result. Use "we" and commands. Teaching pauses link
elsewhere.

**How-to** (action + work). Steps to a goal. Solve a problem a person has, not an
operation the machine can perform. Assume competence and skip teaching. Action
only, no background. Conditional forks are fine. Name it after the task.

**Reference** (understanding + work). Facts for lookup. Describe. Only describe.
No instruction, no opinion. Dry, complete, certain. Mirror the structure of the
thing described. Generate it from code where you can.

**Explanation** (understanding + learning). One bounded topic, readable away from
the product. Anchor on a real "why" question. Design decisions, history,
constraints, and alternatives. **Opinion is permitted here and nowhere else.**

## Don't mix modes

No reference tables inside a tutorial, no tutorial hand-holding inside reference,
no arguing inside a how-to. **Split and link instead.**

## The core three

1. Cut every word doing no work.
2. Use short, everyday words over long ones.
3. Fix sentences that sound machine-written by another method.

## Sentences and paragraphs

- One instruction per sentence; one thought per sentence elsewhere.
- Split instructions over ~20 words, other sentences over ~25.
- Place conditions before the step they guard: "To delete a deck, click Delete."
- Commands, never narration or passive voice.
- Minimize "-ing" words. Keep "the" and "a" where they aid clarity.
- Mix sentence lengths on purpose. Read an awkward sentence aloud and rewrite it.
- Headings carry the point, not just the topic.
- Numbered lists for sequences, bullets otherwise. Introduce a list with a
  complete sentence.

## Never write

Passive voice (unless the actor is unknown or irrelevant) · hedging ("should be
done", "simply", "easy") · buzzwords and figurative language · pre-announcements
· repeated sentence starters · a slash where "a, b, or both" is meant · em dashes
(use a period) · parenthetical plurals like `field(s)` · idioms, colloquialisms,
Latin abbreviations · two names for one thing · dropped verbs in parallel
structures · misplaced "only" and "not" · ambiguous "it", "they", "this" · long
noun strings without breaks.

## Slop

The [unslop skill](../SKILL.md) owns the content, language, style and chatbot
tells, and how to put a voice back. It applies to everything a person reads,
not only docs. Use the project's writing checks where available.

This file owns the other half: which mode a document is in, and how its
sentences are built.

## Review checklist

1. Each file is one mode, linked where modes meet.
2. Every instruction is a command with its condition first.
3. No sentence carries two instructions or two thoughts.
4. Every word means something.
5. "Only" sits next to its word; every pronoun points at one thing; clauses keep
   their verbs.
6. Each thing has exactly one name, here and in the code.
7. Plain words developers say aloud, and real symbol names.
8. Every symbol, path and count is real at commit, with the command that
   regenerates it.
