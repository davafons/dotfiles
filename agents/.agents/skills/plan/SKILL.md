---
name: plan
description: "Plan and review David's day across Fizzy tasks and HEY Calendar. Use for daily planning, prioritization, time-blocking, and completed-work reviews."
---

# Plan

Build a realistic day from two connected sources of truth:

- Fizzy records the work David intends to complete and what he completed.
- HEY Calendar records appointments and when work is planned.

Read both before proposing a plan. Surface time conflicts, travel or focus needs, and important unscheduled tasks. Treat an existing calendar commitment as fixed unless David asks to move it. Fit tasks around it with realistic buffers.

When David asks to organize, plan, or time-block the day, first present a compact proposed schedule. After approval, create the requested time blocks through `calendar`, keep each linked task's `Planned:` line current through `tasks`, and move genuinely intended work into `Today`. Do not create duplicate HEY todos or duplicate task records.

For detailed task actions use `tasks`. For calendar edits and time blocks use `calendar`. If David explicitly asks to journal or preserve a reflection, use the Obsidian adapter without turning the daily plan into a duplicate task system.

## Review today

When David asks what he did today or requests a daily review:

1. Through `tasks`, use the runtime's internal Fizzy adapter manual to read
   cards closed today across the relevant boards.
2. Through `calendar`, use the runtime's internal HEY adapter manual to read
   today's calendar events.
3. Separate completed work from attended/planned time. Mention unfinished
   `Today` tasks briefly; do not count them as accomplishments.
4. Return a compact factual review. Only write a journal note when David asks.

HEY may return a recurring series with its original timestamp rather than the
occurrence date. Do not count it as today's activity unless the returned data
actually establishes an occurrence today; state the uncertainty briefly.

This is a read-only review by default. Do not create an audit-log subsystem or
duplicate completion history outside Fizzy.
