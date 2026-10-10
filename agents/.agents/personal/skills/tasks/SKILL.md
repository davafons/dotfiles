---
name: tasks
description: "Capture, organize, and complete David's actionable work. Use for ordinary tasks; coordinate with Calendar when a task has a time."
---

# Tasks

Tasks are tracked in Fizzy. Treat Fizzy as the source of truth for meaningful work that David intends to complete and review later. Do not turn every calendar reminder or routine into a Fizzy card.

- Put errands and life administration in `Personal`.
- Put finite product or engineering work in `Projects`, with one project tag.
- Put continuing areas such as study or photography in `Ongoing`.
- Use `Next`, `Today`, `Doing`, and `Done` as workflow states. Keep `Today` small and intentional.

Before using the Fizzy CLI, read its internal provider reference. Use
`$PERSONAL_SKILLS_PROVIDER_DIR/fizzy/SKILL.md` when that variable is set;
otherwise use `~/.agents/skills/fizzy/SKILL.md`. Provider details are
intentionally hidden from normal skill discovery; do not copy them into this
facade. Resolve the target board and check for an existing matching card
before a write. Read the card back afterward. If another agent changed the
same card, refresh and reconcile once instead of blindly retrying. Different
cards may be handled in parallel.

Interpret natural capture requests by their commitment:

- "Add groceries to my list" creates a `Personal` task.
- "I have to do groceries today" is calendar-only when it is just a timed errand; create a `Personal` task when David wants a checklist, shopping plan, or completion history.
- Meetings with friends, appointments, workouts, meals, chores, and simple reminders are calendar-native by default, not Fizzy tasks.
- Recurring routines such as gym sessions belong in HEY `habit` plus calendar occurrences, not a new Fizzy card each time.
- If the request is substantive work, multi-step, needs follow-up, or explicitly asks for a task, create or locate the Fizzy task. If it also has a date or time, hand off to `calendar` for the time block. A time block never replaces a meaningful task.
- Prefer one card with a description or checklist for a coherent piece of work over many tiny cards. Keep `Today` small and intentional.

For a task-linked time block, keep a concise current `Planned:` line in the card description. Add the provider-returned calendar event permalink when one is available; otherwise record the HEY event ID, local date/time, and calendar name rather than constructing an unverified URL. The matching calendar event carries the direct Fizzy card link or number. If the user later completes the task, close the card; do not remove its planning history. On a meaningful reschedule, retain the old value as a brief `Previously planned:` line; otherwise keep only the current plan. Calendar-only activities retain their history in HEY and do not need a duplicate card.

For a combined day plan, prioritization, or time-blocking request, use `plan`.
For board migrations, tags, columns, exports, and other structural changes,
stay within this facade and apply the Fizzy adapter's advanced instructions.
