---
name: how
description: "Use for \"how does X work\", code walkthroughs before changing something, and placement / ownership / layering questions (\"where should this live\", \"which package owns this\", \"is this the right layer\"). Explains subsystem architecture, runtime flow, onboarding mental models. Use why for motivation."
license: MIT
metadata:
  upstream: https://github.com/cursor/plugins/tree/d73344bee8cf22e53b9d5f4cf5749d38ba38c174/pstack/skills/how
  revision: d73344bee8cf22e53b9d5f4cf5749d38ba38c174
---

# How

Explain how a subsystem works from its code. Give a senior engineer enough of
an architectural model to work on it, not an annotated source listing.

## Runtime adaptation

Read the [shared working rules](../dav-mode/references/working-rules.md).
Keep the investigation read-only, including external tools and services.
Use the file reads and CLI searches available in the current harness.

Investigate and explain directly, serially, unless the user explicitly requests
delegation or parallel work. Do not claim independent review for your own work.
When delegation is authorized, use the harness's child API and configured models.
Follow its start-and-wait lifecycle. Pass scoped briefs and the shared working rules.

Use the reference templates as exploration and writing checklists.
Adapt their tool names and references to other agents to the actual execution.

## Workflow

1. **Scope the question.** If ambiguous, state your interpretation and explore.
   For a narrow question, investigate in one pass. For a broad subsystem,
   divide it into distinct exploration angles without duplicating work.
2. **Trace the code.** Follow the
   [explorer checklist](references/explorer-prompt.md).
   Find the entry point, follow data through calls, and identify abstractions
   and boundaries. Record exact files and symbols, surprises, and gaps.
3. **Build the explanation.** Use the
   [explainer checklist](references/explainer-prompt.md).
   Combine the findings and resolve contradictions against the code.
   Do not restart the investigation unless a gap requires it.
4. **Present what the code supports.** Explain the flow with concrete file and
   symbol references. State what you could not trace. Use the applicable output
   sections: Overview, Key Concepts, How It Works, Where Things Live, Gotchas.
   Drop sections that do not help answer the question.
