---
name: principle-redesign-from-first-principles
description: "Apply when integrating a new requirement into an existing design."
disable-model-invocation: true
license: MIT
metadata:
  upstream: https://github.com/cursor/plugins/tree/101b274dd991f694e1f7024be2157e5f3adf07de/pstack/skills/principle-redesign-from-first-principles
  revision: 101b274dd991f694e1f7024be2157e5f3adf07de
---

# Redesign From First Principles

When integrating a change, don't bolt it onto the existing design. Redesign as if the requirement had been a foundational assumption from the start.

- Read all affected files and understand the current design
- Ask: "if we were writing this from scratch with this new requirement, what would we build?"
- Propagate the change through every reference: types, docs, examples, rationale sections
- Think about the whole redesign, then deliver it incrementally

This is the method for preserving option value when integrating changes into an existing design.
