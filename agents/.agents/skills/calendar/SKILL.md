---
name: calendar
description: "Manage David's appointments and time blocks. Coordinate with Tasks for timed work; use for scheduling, rescheduling, reminders, and protected time."
---

# Calendar

The calendar is the source of truth for when David has committed time. Before
using the HEY CLI, read its internal adapter manual. Use
`$PERSONAL_SKILLS_ADAPTER_DIR/hey/SKILL.md` when that variable is set;
otherwise use `~/.agents/skills/hey/SKILL.md`. The provider skill is
intentionally hidden from normal skill discovery; do not copy its manual into
this facade.

- Always use `Asia/Tokyo` and JST wall times for new or edited events.
- Resolve the intended calendar before a write. Do not rely on HEY's default calendar.
- For timed task blocks, default to reminders 10 minutes and 1 minute before the start (`--remind 10m --remind 1m`) unless the user specifies a different reminder pattern.
- Use calendar events for appointments, travel, and protected time blocks. Do not create a HEY todo as a second copy of a Fizzy task.
- When a request names both work and a time, create or locate the Fizzy task through `tasks`, then create the calendar time block. Put the direct Fizzy card link or number in the event notes/link, and put the direct calendar event link in the task description alongside its `Planned:` line; the task remains the completion record and the event records the plan.
- Update the task's concise `Planned:` line when scheduling or rescheduling it. Do not use tags as a substitute for the actual time.
- Check for an existing matching event before creating one, and verify every
  write by reading it back. If another agent changed the same event, refresh
  and reconcile once instead of blindly retrying. Different events may be
  handled in parallel.

For ordinary task capture or completion use `tasks`. For a combined daily agenda, prioritization, or time-blocking request use `plan`. Direct HEY mail work belongs to `mail`.
