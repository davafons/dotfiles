# Dav's Fizzy Solo Sprint Workflow

> Personal notes for using Fizzy as a solo task system. Derived from real CLI quirks discovered in practice.

## My Board Structure

| Board | Purpose |
|-------|---------|
| **Personal** | Day-to-day life admin |
| **Nadeshiko** | Media splitting project |
| **Instagram** | Content creation (@davenjapon) |
| **JLPT N1 Summer** | Japanese study tracking |
| **davafons.com** | Website/blog |
| **Wariwari** | Side project |
| **Home Server** | Infrastructure |
| **Photography** | Photo organization |
| **humancoverage.dev** | Another side project |

## Column Workflow (per board)

Standard columns I use:
- `Maybe?` = Backlog (default for new cards)
- `This Week` = Current sprint (~3-7 cards max)
- `Today` = Today's shortlist (~1-3 cards)
- `In Progress` = Active work (ideally 1 card)
- `Waiting` = Blocked / external dependency
- `Done` = Finished (pseudo-column)
- `Not Now` = Intentionally deprioritized

## CLI Quirks I Keep Hitting

**Auth fails with "No account configured":**
If `~/.config/fizzy/config.yaml` has `account: ""` (empty), you must set it via env:
```bash
export FIZZY_ACCOUNT=6104339  # your account slug without the /
```

Or use `--account` flag on every command. Check your account slug:
```bash
fizzy identity show | jq '.data.accounts[0].slug'  # returns "/6104339"
# Use just the number: 6104339
```

**No assignee on create:**
```bash
# This doesn't work: fizzy card create --assignee ...
# Have to do it in two steps:
fizzy card create --title "Thing" --board BOARD_ID
fizzy card self-assign CARD_NUMBER
```

**No column reordering:**
`fizzy column move-left/move-right` doesn't actually work. To reorder:
1. List columns: `fizzy column list --board BOARD_ID`
2. If needed, delete/recreate columns in desired order
3. Temporarily park cards in `Maybe?` during reshuffling

## Time Estimates via Tags

Fizzy has no native estimates. Use tags with `~` prefix for time:
- `~15m`, `~30m` — quick wins, batch these
- `~1h`, `~2h`, `~3h` — standard tasks
- `~4h`, `~6h`, `~8h` — heavy tasks, usually not splittable

**Tag a card:**
```bash
fizzy card tag CARD_NUMBER --tag "~3h"
```

**Why `~` prefix:** Makes time tags visually distinct from topic tags in the UI.

## Prioritization: Golden Tickets + "This Week"

Two-tier system for capacity planning:

| Tier | Method | Purpose |
|------|--------|---------|
| **Strategic** | Golden star (⭐) | Marks "must do soon" across all boards |
| **Tactical** | "This Week" column | What I'm actually doing this week |

**Workflow:**
1. **Friday planning:** Review all boards, mark golden tickets for next week's focus
2. **Capacity check:** Sum time estimates, adjust to ~25h (not 40h — realistic side-project bandwidth)
3. **Move to "This Week":** Pull golden tickets + any quick wins into "This Week" column
4. **Morning:** Pick 1-3 cards from "This Week" into "Today"

**When over capacity:** Move heavy tasks back to "Maybe?", keep the lean set. Better to finish 6 cards than start 12.

## Useful Snippets

**Bulk self-assign unassigned cards:**
```bash
nums=$(fizzy card list --account 6104339 --board BOARD_ID --all | jq -r '.data[] | select((.assignees|length)==0) | .number')
while IFS= read -r n; do
  [ -n "$n" ] && fizzy card assign "$n" --account 6104339 --user USER_ID >/dev/null
done <<< "$nums"
```

**Get my user ID:**
```bash
fizzy identity show | jq '.data.accounts[0].user.id'
```

**Check board columns:**
```bash
fizzy column list --account 6104339 --board BOARD_ID | jq '[.data[] | {name,id,pseudo}]'
```

## Weekly Planning Routine

**Friday (~30 min):**
1. List all open cards across boards
2. Tag any untagged cards with time estimates (`~30m`, `~2h`, etc.)
3. Mark strategic priorities as golden
4. Sum estimates for golden cards, adjust to ~25h capacity
5. Move selected cards to "This Week" columns
6. Push excess back to "Maybe?"

**Quick wins to batch (15-30m each):**
Good filler when you have 30m before a meeting. Look for `~15m` and `~30m` tags.

## Sprint Cadence

- **1-week sprints** for solo work (more responsive than 2-week)
- Friday afternoon: review "This Week", plan next week
- Morning: pick 1-3 cards from "This Week" into "Today"
- WIP limit: 1 "In Progress" card when possible

**Capacity reality check:**
- Full-time job: ~25h/week for side projects (not 40h)
- Honest estimates: If you always underestimate, add 50% buffer
