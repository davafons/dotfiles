---
name: tasks
description: "Capture, organize, and complete David's actionable work. Use for ordinary tasks; coordinate with Calendar when a task has a time."
---

# Tasks

Tasks are tracked in Fizzy. Treat Fizzy as the source of truth for what needs doing and whether it was done.

- Put errands and life administration in `Personal`.
- Put finite product or engineering work in `Projects`, with one project tag.
- Put continuing areas such as study or photography in `Ongoing`.
- Use `Next`, `Today`, `Doing`, and `Done` as workflow states. Keep `Today` small and intentional.

Before using the Fizzy CLI, read its internal adapter manual. Use
`$PERSONAL_SKILLS_ADAPTER_DIR/fizzy/SKILL.md` when that variable is set;
otherwise use `~/.agents/skills/fizzy/SKILL.md`. The provider skill is
intentionally hidden from normal skill discovery; do not copy its manual into
this facade. Resolve the target board and check for an existing matching card
before a write. Read the card back afterward. If another agent changed the
same card, refresh and reconcile once instead of blindly retrying. Different
cards may be handled in parallel.

Interpret natural capture requests by their commitment:

- "Add groceries to my list" creates a `Personal` task.
- "I have to do groceries today" creates or moves it to `Personal` / `Today`.
- If the user supplies a date or time, create or locate the Fizzy task and hand off to `calendar` to create or update the time block. A time block never replaces the task.

For a scheduled task, keep a concise `Planned:` line in the card description with the local date and time. The matching calendar event carries the Fizzy card reference. If the user later completes the task, close the card; do not remove its planning history.

For a combined day plan, prioritization, or time-blocking request, use `plan`.
For board migrations, tags, columns, exports, and other structural changes,
stay within this facade and apply the Fizzy adapter's advanced instructions.
