---
name: how
description: "Use for \"how does X work\", code walkthroughs before changing something, and placement / ownership / layering questions (\"where should this live\", \"which package owns this\", \"is this the right layer\"). Explains subsystem architecture, runtime flow, onboarding mental models. Use why for motivation."
disable-model-invocation: true
license: MIT
metadata:
  upstream: https://github.com/cursor/plugins/tree/1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def/pstack/skills/how
  revision: 1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def
---

# How

Explore the codebase to answer "how does X work?" questions. Produce architectural explanations at the level of a senior engineer onboarding onto a subsystem, enough to build a working mental model, not so much that it reads like annotated source code.

## Runtime adaptation

Read the [shared working rules](../dav-mode/references/working-rules.md) and
[playbook runtime](../dav-mode/references/playbook-runtime.md).
Keep all investigation read-only. Use jj for repository history and
`jj diff --git` for patches.

Use the current harness's child API and configured explorer and explainer roles
when delegation is explicitly authorized. Inherit configured defaults when a
role is unavailable. Do not assume Cursor Task fields, a `pstack-models.mdc`
file, per-call model selection, or a read-only sandbox. Follow the native child
lifecycle and pass scoped read-only briefs with the shared-desktop restrictions.

Without delegation permission, perform the same explorer angles and explainer
pass directly, in sequence. Do not claim independent exploration or synthesis.
For the simple path, omit the explorer-findings section and use only the
explainer template. For the complex path, preserve each angle's findings and
pass every finding into synthesis.

## 1. Assess complexity

If the scope is ambiguous, state your interpretation and explore. The user can redirect.

- **Simple** (a single module, a small utility, a narrow question such as "how does function X work"): no explorers. Run one explainer that explores and explains in one pass, built from `references/explainer-prompt.md` without the explorer-findings section. Go to step 4.
- **Complex** (a subsystem spanning multiple files or services, a cross-cutting feature, a full architectural overview): go to step 2.

When in doubt, take the simple path.

## 2. Explore (complex only)

Decompose the question into 2 to 4 angles, each a distinct slice of the subsystem. When delegation is authorized, spawn all explorers in a single message, each with `references/explorer-prompt.md` and its angle filled in.

## 3. Synthesize (complex only)

Once all exploration is complete, run one explainer with `references/explainer-prompt.md` and every explorer's findings filled in.

## 4. Present

Present the explainer's output. Light edits for clarity or context from the conversation are fine. Do not substantially rewrite it.

## Output format

The explanation uses the sections defined in `references/explainer-prompt.md`, dropping any that do not apply: Overview, Key Concepts, How It Works, Where Things Live, Gotchas.
