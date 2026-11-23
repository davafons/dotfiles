---
name: calendar
description: "Manage David's appointments, time blocks, and recurring routines in Google Calendar. Coordinate with Tasks for meaningful timed work."
---

# Calendar

The calendar is the source of truth for when David has committed time. It is
Google Calendar on `davafons@gmail.com`, used through `gcalcli` (OAuth in
`~/Library/Application Support/gcalcli/`). HEY Calendar is retired; do not use
the `hey` CLI.

## Calendars

- `Personal`: ordinary commitments, appointments, chores, meals, protected work blocks, personal time off (all-day event spanning the dates).
- `Social`: trips, meetups, concerts and other fixed external plans.
- `Training`: the workout plan.
- `Routines`: daily routines (meals, bedtime).
- `Maybe`: only genuinely tentative plans.
- Read-only context, never write targets: Google's Japanese holidays calendar, the work calendar (free/busy only), and the old Google calendars (`Events`, `Sleep`, `TickTick`, `Japanese`, `Routine`, `Birthdays`).

## Commands

Add `--nocolor` when reading output. Always pass `--calendar` and, for writes, `--noprompt`.

| Need | Command |
|---|---|
| List calendars | `gcalcli list` (`gcalcli --refresh list` after calendars change) |
| Agenda | `gcalcli --nocolor agenda` (today + 5 days) or `gcalcli --nocolor agenda 2026-11-25 2026-12-02` |
| One calendar | `gcalcli --calendar Personal agenda …` |
| Machine-readable | `gcalcli agenda --tsv --details all …` |
| Find | `gcalcli search "Gym" 2026-11-01 2026-12-31` |
| Add timed | `gcalcli add --calendar Personal --title "X" --when "2026-11-27 15:00" --duration 60 --reminder 10m --reminder 1m --noprompt` (`--where`, `--description`) |
| Add all-day | `gcalcli add --calendar Personal --title "X" --allday --when 2026-11-27 --duration 1 --noprompt` (duration in days) |
| Delete | `gcalcli --calendar Personal delete "X" 2026-11-27 2026-11-28 --iamaexpert` |
| Edit | `gcalcli edit` is interactive: delete and re-add instead |
| Recurring | `gcalcli add` cannot create one; use `gcalcli import file.ics` or ask David to use the web UI |

If gcalcli fails with an auth error, the login was revoked: tell David it needs `gcalcli init` again (the Google Cloud app `gcalcli-515801` is published, so logins no longer expire weekly).

## Rules

- Always use `Asia/Tokyo` and JST wall times.
- Resolve the intended calendar before a write; never rely on the default calendar.
- Check the Japanese holidays calendar when planning around likely days off; never copy its events.
- Meetings with friends, appointments, travel, workouts, meals, chores, and simple reminders are calendar-native and do not need Fizzy cards by default.
- For actionable personal events (task-linked work, errands, chores, workout sessions), default to reminders 10 minutes and 1 minute before (`--reminder 10m --reminder 1m`) unless David asks otherwise.
- For `Social`, use 1 day and 1 hour before timed events, and 1 day before for all-day events.
- There is no habit tracker any more (HEY Habits is gone). Workouts are planned as `Training` events; an event does not prove the session happened. Ask David before inventing a completion record.
- When substantive work names both work and a time, create or locate the Fizzy task through `tasks`, then create the time block. Put the Fizzy card link in the event description, and the event link (`--details url`) with a concise `Planned:` line in the task description. The task remains the completion record.
- When rescheduling a task-linked event, keep `Planned:` current; add a short `Previously planned:` note only when the change is meaningful.
- Check for an existing matching event before creating one, and verify every write by reading it back. If another agent changed the same event, refresh and reconcile once instead of blindly retrying.

For ordinary task capture or completion use `tasks`. Mail belongs to `mail`.
