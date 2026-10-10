---
name: unslop
description: Cut AI tells from any writing. Must always apply.
metadata:
  origin: shirabe
  origin-path: docs/agents/unslop.md
  origin-revision: 968e24d69837e3efecca31487f7d8e8508e803c8
---

Read the [shared working rules](../dav-mode/references/working-rules.md) before applying this skill.
Project instructions supply the commands and conventions; examples are not prerequisites.

# unslop

Applies to anything you write that a person reads: UI copy, changelog notes,
locale strings, docs, commit messages, PR bodies, a comment that survived. Not a
polish pass you reach for. A gate before the text lands.

**Best used by never firing.** The cleanup-afterward pass is measured to fail:
the sentence you would have to remove is easier not to generate than to catch.
Write it clean as you draft it, and keep this list for the pass over text that
is already written.

## 1. Scan

**Content tells.** Puffery ("pivotal moment", "testament to", "evolving
landscape") · name-dropping without context · hollow -ing phrases
("highlighting", "ensuring", "fostering") · promotional adjectives ("vibrant",
"breathtaking", "stunning") · vague attribution ("experts believe", "reports
suggest") · formulaic problem-then-solution shapes.

**Language tells.** "Additionally", "crucial", "delve", "enduring", "enhance" ·
"serves as" / "stands as" / "boasts" where "is" works · "not just X, but Y" ·
forced groups of three · the same idea restated with a synonym a line later.

**Style tells.** Em dashes and mid-sentence colons used as connectors ·
excessive bold · title case headings · decorative emoji · curly quotes · generic
inline-header lists ("**Performance:** performance is…").

**Other tells.** Chatbot phrases ("I hope this helps!", "Great question!") ·
filler and hedging · abstract metaphor nouns (substrate, vector, wedge,
paradigm) · passive voice where the actor is knowable · weak verbs propped up by
adverbs.

## 2. Rewrite

Keep the meaning and the intended tone. Remove the pattern, not the point.

## 3. Put a voice back

Hold an opinion. Vary the sentence rhythm. Admit complexity rather than
smoothing it. Be specific: a number, a filename, a real example. First person
where it is honest. Let some imperfection stand.

## 4. Self-audit

Ask: **what makes this obviously machine-made?** Fix what is left.

## Output

The revised text. Optionally the sections you changed and why.

For documents, also read [Writing](references/writing.md): one Diátaxis mode
per file, sentence construction, and the review checklist.
