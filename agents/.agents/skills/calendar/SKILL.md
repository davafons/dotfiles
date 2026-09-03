---
name: calendar
description: "Manage David's appointments and time blocks. Coordinate with Tasks for timed work; use for scheduling, rescheduling, reminders, and protected time."
---

# Calendar

The calendar is the source of truth for when David has committed time. Use the installed `hey` CLI as the internal adapter.

- Always use `Asia/Tokyo` and JST wall times for new or edited events.
- Resolve the intended calendar before a write. Do not rely on HEY's default calendar.
- Use calendar events for appointments, travel, and protected time blocks. Do not create a HEY todo as a second copy of a Fizzy task.
- When a request names both work and a time, create or locate the Fizzy task through `tasks`, then create the calendar time block. Put the Fizzy card link or number in the event notes; the task remains the completion record and the event records the plan.
- Update the task's concise `Planned:` line when scheduling or rescheduling it. Do not use tags as a substitute for the actual time.
- Verify a newly written event by reading it back before reporting its time.

For ordinary task capture or completion use `tasks`. For a combined daily agenda, prioritization, or time-blocking request use `plan`. Direct HEY mail work belongs to `mail`.
