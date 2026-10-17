---
name: deslop
description: Remove AI-generated code slop and clean up code style
---

# Remove AI code slop

Read the [shared working rules](../dav-mode/references/working-rules.md).
Source: [cursor/plugins `101b274d`](https://github.com/cursor/plugins/blob/101b274dd991f694e1f7024be2157e5f3adf07de/cursor-team-kit/skills/deslop/SKILL.md).

Check the diff against main and remove AI-generated slop introduced in the branch.

## Focus Areas

- Extra comments that are unnecessary or inconsistent with local style
- Defensive checks or try/catch blocks that are abnormal for trusted code paths
- Casts to `any` used only to bypass type issues
- Deeply nested code that should be simplified with early returns
- Other patterns inconsistent with the file and surrounding codebase

## Guardrails

- Keep behavior unchanged unless fixing a clear bug.
- Prefer minimal, focused edits over broad rewrites.
- Keep the final summary concise (1-3 sentences).
