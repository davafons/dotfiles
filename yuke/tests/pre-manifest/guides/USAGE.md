# Usage dashboard

Restart Yuke after installing the profile, then run `/usage` for global history or `/usage current` for the current workspace.

## Navigate

| Key | Action |
| --- | --- |
| `1` through `6` | Overview, Usage, Messages, Plugins, Skills, Chats |
| `Tab` / `Shift+Tab`, `l` / `h` | Next or previous tab |
| `g` | Daily, weekly, or monthly usage; weeks start Monday |
| `s` | Global or current-workspace history |
| `r` | Refresh |
| `j` / `k`, arrows, mouse wheel | Scroll; select a chat in Chats |
| `Ctrl+d` / `Ctrl+u`, Page Down / Page Up | Move a page |
| Home / End | First or last row |
| `/` in Chats | Filter by title, workspace, model, id, or kind; blank clears |
| Enter in Chats | Resume the selected chat |
| Escape, `q`, `Ctrl+c` | Close |

Tabs and period/scope/refresh controls accept mouse clicks. Double-click a chat title to resume it. Narrow terminals show fewer heatmap weeks when a full year does not fit.

Blue marks headings and navigation, cyan marks tokens and tools, violet marks reasoning and skills, and green marks savings and healthy states. Costs and incomplete-data notes are amber; failures are red. The colors follow the profile's dark/light and truecolor/256-color palettes.

## Read the numbers

The dashboard reads the local Yuke SQLite store, including child sessions, without contacting providers. It requires `python3` with SQLite support. Chat counts separate top-level chats from children; usage totals include both.

- Total tokens are input plus output. Cache tokens are subsets of input; reasoning is a subset of output.
- Costs use Yuke's recorded prices, not subscription charges. Missing prices or token counts are flagged as partial totals.
- Input/output percentages use total tokens; reasoning uses output; cache reads/writes and uncached input use input. Uncached input excludes both cache reads and writes.
- Cost and savings percentages use the estimated no-cache cost for priced replies. Saving 80% means paying 20% of that estimate, not saving 80% of the amount paid.
- Percentages use summed counts and costs, not averages of per-reply rates. They show one decimal place, or `n/a` when the denominator is zero.
- Peak tokens means the busiest local calendar day. Streaks count days with recorded assistant activity; yesterday's streak remains current until today ends.
- Longest chat is first-to-last message time, including idle gaps. Run time sums completed runs, including children, not time spent at the keyboard.
- Plugins lists currently loaded plugins. Yuke does not retain historical plugin run counts. The same tab ranks tool calls, errors, cancellations, and durations.
- Skill uses count recorded invocations and successful reads of known skill files, once per skill per run. Invocations and reads are also shown separately. Merely mentioning a skill does not count.

Global covers this local profile, not other machines or Codex history. Deleted sessions disappear. If retained lifetime totals differ from the event history, the dashboard flags it; daily/model breakdowns cover retained events.

## Verify

```sh
python3 ~/.config/yuke/tests/check-usage-data.py --real ~/.local/share/yuke/yuke.db
python3 ~/.config/yuke/tests/check-usage.py
yuke check
```

The TUI check requires `tmux`. It uses a detached test session and isolated XDG directories, saves screen captures, and cleans up. It never attaches to your terminal or sends model requests. Temporary usage snapshots have private permissions and are removed after reading.
