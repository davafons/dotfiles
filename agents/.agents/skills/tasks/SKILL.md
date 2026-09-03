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

Use the installed `fizzy` CLI as the internal adapter. Resolve the target board before a write and make changes only when the user has clearly requested them.

Interpret natural capture requests by their commitment:

- "Add groceries to my list" creates a `Personal` task.
- "I have to do groceries today" creates or moves it to `Personal` / `Today`.
- If the user supplies a date or time, create or locate the Fizzy task and hand off to `calendar` to create or update the time block. A time block never replaces the task.

For a scheduled task, keep a concise `Planned:` line in the card description with the local date and time. The matching calendar event carries the Fizzy card reference. If the user later completes the task, close the card; do not remove its planning history.

For a combined day plan, prioritization, or time-blocking request, use `plan`. Board migrations, tags, columns, exports, and other structural changes belong to the explicit `$fizzy` adapter skill.
