---
name: principle-guard-the-context-window
description: "Apply when context is filling up: large outputs, long files, repeated reads, fan-out planning. Route bulk to subagents; keep summaries in the main thread, not raw payloads."
disable-model-invocation: true
license: MIT
metadata:
  upstream: https://github.com/cursor/plugins/tree/101b274dd991f694e1f7024be2157e5f3adf07de/pstack/skills/principle-guard-the-context-window
  revision: 101b274dd991f694e1f7024be2157e5f3adf07de
---

# Guard the Context Window

**Why:** Context overflow degrades reasoning quality, creates compression artifacts, and halts progress.

**Pattern:**

- **Size phases and cap scope.** Limit files per phase, set turn budgets, account for mechanism costs.
