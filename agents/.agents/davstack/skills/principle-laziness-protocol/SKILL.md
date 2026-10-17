---
name: principle-laziness-protocol
description: "Apply when refactoring, evaluating diff size, or tempted to add abstractions, layers, or signal threading. Bias toward deletion and the smallest change that solves the problem."
disable-model-invocation: true
license: MIT
metadata:
  upstream: https://github.com/cursor/plugins/tree/101b274dd991f694e1f7024be2157e5f3adf07de/pstack/skills/principle-laziness-protocol
  revision: 101b274dd991f694e1f7024be2157e5f3adf07de
---

# Laziness Protocol

- **Consolidate decisions.** Do not repeat the same choice in several places. Put it behind one source of truth and pass the result as a simple flag.
- **Minimize the diff.** Make the smallest change that solves the problem. Fewer lines beat "elegant" boilerplate.
