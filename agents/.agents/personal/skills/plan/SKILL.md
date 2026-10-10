---
name: plan
description: "Plan and review David's day across Fizzy tasks, HEY Calendar, and HEY Habits. Use for daily planning, prioritization, time-blocking, routine cadence, and completed-work reviews."
---

# Plan

Build a realistic day from three connected sources of truth:

- Fizzy records the work David intends to complete and what he completed.
- HEY Calendar records appointments and when work is planned.
- HEY Habits records recurring routines and their cadence/completions.

Read all three before proposing a plan: use a seven-day lookback for unfinished/recent tasks and calendar commitments, and a fourteen-day lookback for habit cadence and completions. Include relevant external calendar context, especially `日本の祝日`, so Japanese national holidays and likely days off affect the proposal without being copied into a writable calendar. Use that history to make bounded suggestions, such as recommending a gym day when the weekly cadence is falling behind; distinguish an inference from a recorded commitment and briefly state its basis. A past calendar event proves that something was scheduled, not that it happened. Treat an existing calendar commitment as fixed unless David asks to move it. Fit tasks around it with realistic buffers. If history is missing, label the recommendation as preference-based rather than predictive.

When David asks to organize, plan, or time-block the day, first present a compact proposed schedule that labels each item as task-linked, calendar-only, or habit-based. After approval, create only the appropriate records: use `calendar` for calendar-native activities and habits, and use `tasks` plus `calendar` for substantive task-linked work. Keep each linked task's `Planned:` line current through `tasks`, move genuinely intended work into `Today`, and prefer descriptions/checklists over many tiny cards. Do not create duplicate HEY todos or duplicate task records.

For detailed task actions use `tasks`. For calendar edits and time blocks use `calendar`. If David explicitly asks to journal or preserve a reflection, use the Obsidian adapter without turning the daily plan into a duplicate task system.

## Daily operating loop

- At the start of a planning request, read today's calendar, due habits, Fizzy `Today` work, and the recent lookbacks before proposing a schedule.
- During the day, treat explicit user updates as completion evidence: close a completed Fizzy card or mark the relevant HEY habit complete. Do not infer completion merely because a calendar event elapsed.
- For a closeout request such as "close out my day" or "review today," report completed Fizzy work, completed habits, and scheduled/attended time separately. Briefly identify unfinished `Today` work.
- After the review, propose tomorrow's priorities and candidate habit sessions. Do not create tomorrow's blocks or move tasks until David approves the proposal.
- Do not proactively message David at day's end unless a separate reminder or automation has been explicitly configured. A recurring closeout event can be created if he wants a prompt.

## Review today

When David asks what he did today or requests a daily review:

1. Through `tasks`, use the runtime's internal Fizzy provider reference to read
   cards closed today across the relevant boards.
2. Through `calendar`, use the runtime's internal HEY provider reference to read
   today's calendar events.
3. Through `calendar`, read relevant habit occurrences/completions.
4. Use evidence levels: a closed Fizzy card is completed work; a completed HEY habit is a completed routine; a calendar event is planned time unless David independently confirms attendance/completion. Separate completed work, completed habits, and attended/planned time. Mention unfinished `Today` tasks briefly; do not count them as accomplishments.
5. Return a compact factual review. Only write a journal note when David asks.

HEY may return a recurring series with its original timestamp rather than the
occurrence date. Do not count it as today's activity unless the returned data
actually establishes an occurrence today; state the uncertainty briefly.

This is a read-only review by default. Do not create an audit-log subsystem or
duplicate completion history outside Fizzy.
