---
name: calendar
description: "Manage David's appointments, time blocks, and recurring routines. Coordinate with Tasks for meaningful timed work."
---

# Calendar

The calendar is the source of truth for when David has committed time. Before
using the HEY CLI, read its internal provider reference. Use
`$PERSONAL_SKILLS_PROVIDER_DIR/hey/SKILL.md` when that variable is set;
otherwise use `~/.agents/skills/hey/SKILL.md`. Provider details are
intentionally hidden from normal skill discovery; do not copy them into this
facade.

- Always use `Asia/Tokyo` and JST wall times for new or edited events.
- Resolve the intended calendar before a write. Do not rely on HEY's default calendar.
- Route ordinary personal commitments, appointments, chores, workouts, meals, and protected work blocks to `Personal` (HEY calendar 692581). Route trips, meetups, concerts, and other fixed external plans to `Events & Travel` (HEY calendar 745611). Use HEY's `Maybe` calendar only for genuinely tentative plans. External calendars such as `Roxy - Archivum` and `日本の祝日` are read-only context, never write targets.
- Check the external `日本の祝日` calendar (HEY calendar 894582) when planning around Japanese national holidays or likely days off. It is a subscribed reference calendar, so do not copy its events into `Personal` or `Events & Travel`.
- Use HEY Calendar as the source of truth for when David is committed. Meetings with friends, appointments, travel, workouts, meals, chores, and simple reminders are calendar-native and do not need Fizzy cards by default.
- Use HEY habits for recurring routines such as exercising several times per week. The habit is the routine's completion/history record. Create a separate calendar event only when David wants an exact protected time or reminder; an event does not complete the habit, and completing a habit does not imply that every planned event happened.
- For actionable personal events (task-linked work, errands, chores, or exact-time habit sessions), default to reminders 10 minutes and 1 minute before the start (`--remind 10m --remind 1m`) unless the user specifies a different reminder pattern. Preserve ordinary meeting/invite reminder behavior unless David asks to change it.
- Use calendar events for appointments, travel, and protected time blocks. Do not create a HEY todo as a second copy of a Fizzy task.
- When substantive work names both work and a time, create or locate the Fizzy task through `tasks`, then create the calendar time block. Put the direct Fizzy card link or number in the event notes/link. Put the provider-returned calendar event permalink in the task description alongside its `Planned:` line when available; otherwise record the HEY event ID, local date/time, and calendar name. The task remains the completion record and the event records the plan.
- When the activity is calendar-native, create only the event or habit. Do not manufacture a Fizzy card solely to make a reminder or retrospective entry.
- When rescheduling a task-linked event, keep `Planned:` current and preserve a short `Previously planned:` note only when the change is meaningful; do not accumulate a full scheduling log in the card description.
- Update the task's concise `Planned:` line when scheduling or rescheduling it. Do not use tags as a substitute for the actual time.
- Check for an existing matching event before creating one, and verify every
  write by reading it back. If another agent changed the same event, refresh
  and reconcile once instead of blindly retrying. Different events may be
  handled in parallel.

For ordinary task capture or completion use `tasks`. For a combined daily agenda, prioritization, or time-blocking request use `plan`. Direct HEY mail work belongs to `mail`.
