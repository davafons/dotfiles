# Rust migration

Rust source is `~/workspace/yuke`, branch `davafons/rust-plugins`, based on upstream `ea1096b5b8b7`.
The native changes are one published commit, `9a0c9932e0497445b187095178c854c134be8638`, on `origin/davafons/rust-plugins`.
The original Zig checkout is archived at `~/workspace/yuke-zig`, with its pending changes and linked jj workspaces intact.
The Zig source contents and unrelated dotfiles changes stay unchanged.

The default command uses the Rust profile `~/.config/yuke-rust` and data directory `~/.local/share/yuke-rust`.
`yuke-rust` selects the same installation.
`yuke-zig` selects the saved Zig executable and its original profile and data.
The Rust SDK and build identity are in `~/.local/lib/yuke-rust`.
`build.json` records the upstream commit, source hash, and package hash.

The user selected fresh chats.
The migration imports no Zig chat records.
It copies task and inbox databases with SQLite backup and checks every table against the source.
It preserves model aliases, startup model and effort, the personal prompt, provider settings, credentials, and the Monid key.
Credentials use the Rust `auth.json` format and mode `0600`.
The bridge retains Opus, Sonnet, Haiku, and Fable, including image and tool capabilities.
The Zig usage archive contains aggregate totals without chat records.

## Plugin coverage

The profile loads these 26 plugins through public APIs.
The Rust Vim and subagent implementations start from upstream plugins at `3612d4d5`.
The local subagent port also includes the cancellation-report fix from upstream `b1ce906`.

| Plugin | Retained behavior |
| --- | --- |
| navigation | Session navigation, owner-pane fallback, file opening through Herdr Code |
| solarized-theme | Original dark and light colors, true color and 256-color terminals |
| vim | Composer motions, operators, objects, history, registers, transcript motions, selection, search, marks, and raw copy |
| personal | Original prompt, slash-command dispatch, pending Vim command handling |
| web | Monid search and fetch, bounds, polling, cancellation, private key |
| project-work | Shared tasks, claims, notes, progress, messages, GitHub reads, task editing and navigation |
| controls | Pane commands, directional focus, new chat, layered Ctrl+C |
| models | Ready-model and effort pickers, persistent aliases and their editor, startup preferences |
| prompt-history | Saved user prompts, draft restoration, history picker and keys |
| path-completion | Relative and home paths, quoting, directory completion for `/cd` |
| workspace | `/pwd`, canonical `/cd`, destination instructions, idle and single-pane checks |
| session-fork | Completed-event forks, optional destination, source preservation |
| agent-tools | Explicit delegation, general, dav-agent and reviewer roles, receipts, reports, campaign grants |
| dollar-skills | Multiple explicit skills, escaped and code exclusions, original visible input |
| loop | Session-bound timer, stop, cancellation, failure and reload cleanup |
| build-status | Version of the running native host |
| sessions-reworked | Workspace and global session picker, pagination, deletion, owner navigation |
| search | Chat and file search, SQLite FTS, previews, filters, source anchors |
| yuke-clarify | Nonblocking tools, retained drafts, single and batch answers, review, explicit dismissal and adoption |
| herdr | Framed Unix transport, pane state, owner focus, Code file references |
| run-feedback | Cached live phases, reasoning and tool timing, output speed |
| step-trace | Optional metadata-only tool and event-loop diagnostics, off by default |
| peek | Frozen, bounded observer snapshot, separate tool-free requests and cancellation |
| sudo-command | Approved argv, masked password, private transport, redaction, direct `!` commands and saved receipts |
| dashboard | Original centered logo, workspace and model, right-aligned keys, clickable menu, compact layout, commands and device login |
| insights | Status, context budget, saved blocks, prompt and tools, native usage and Zig aggregates |

## Differences that affect use

New composers start in Vim Normal mode.
Tab moves between composer and transcript and retains the transcript caret.
Task editing uses Alt+N, Alt+E, Alt+M, and Alt+U because Rust's editor consumes several old control keys.
Page keys use the Rust names `page_up` and `page_down`.
Reasoning effort appears in the native model status.

A retained pending question still names its old chat.
Open `/questions`, then press Ctrl+O to move it to the current Rust chat.
Confirm the destination before answering.
The move keeps its ID, draft, and original session ID.
It imports no old chat history.
Old task claims stay assigned when their owner cannot be proved closed.
Use the explicit unassign operation for an abandoned claim.

Direct `!` commands save completed-action records without requesting an assistant reply.
A command whose receipt cannot be saved must not run again just to repair the receipt.
`/cd` forks a saved conversation with the destination's instructions.
An unsent draft changes directory without creating a conversation.
`/reload` and exit stop loop timers.
A loop has no saved daemon schedule.

## Verification

Run the full check command from any directory:

```sh
python3 ~/dotfiles/yuke-rust/scripts/verify.py --source ~/workspace/yuke --binary ~/.local/lib/yuke-rust/bin/yuke --native
```

The checks include TypeScript, Biome, 19 plugin-host tests, 123 Vim tests, and 14 Python tests.
The Python tests include sudo transport, inbox transactions, native lock paths, private Herdr IPC, and campaign grants.
The real terminal check covers the dashboard, editing, completion, panes, reload, direct commands, masked sudo, inspections, tasks, search, inbox adoption, and `/cd`.
It checks zero model requests and keeps its fixture password out of terminal output and saved events.
Its sudo fixture runs as the current user and does not invoke real sudo.
The dashboard check verifies all six logo rows in a tall pane, a clickable menu, compact resize, draft visibility, and notices above the dashboard.
The native checks include formatting, clippy, all-feature tests, rustdoc, TypeScript, Biome, and a separate check for each crate.
Logs are in `~/workspace/yuke/target/migration-verification`.

`prepared-check.py` checks copied database tables, aliases, file modes, provider readiness, bridge capabilities, loaded plugins, and a fresh chat store.
It loads the actual prepared profile without sending input or refreshing credentials.
Its zero-chat assertion applies before normal use starts.
Live provider authentication, paid requests, and the user's actual Herdr panes are outside these checks.

## Performance evidence

`benchmark.py` compares the upstream and candidate release binaries through real public frame and editor operations.
Each run checks 300 transcript frames, 600 input frames, 9,000 rows, and source positions.
At the initial migration, five alternating runs per build report zero failures.
Both median wall times are 1.06 seconds.
The baseline range is 1.04 to 1.19 seconds.
The candidate range is 1.04 to 1.09 seconds.
Median peak resident memory is 23,969,792 bytes for upstream and 23,871,488 bytes for the candidate.
No difference exceeds run variation.
CPU time is about one second on one core, and the separate sample places most work in QuickJS and frame conversion.
The comparison does not measure network latency, Zig against Rust, or exact allocation counts.
Raw results and the sample are in `target/migration-benchmark` in the Rust checkout.

## Update or restore the installation

Edit the canonical profile in `yuke-rust/.config/yuke-rust`.
Run the checks.
Run `scripts/prepare.py` to copy profile files without replacing changed Rust state.
Use `--refresh-state` only to refresh migrated files that Rust has not changed.
A changed native binary needs a restart.
The installer saves versioned releases and moves the public link after verification.

To rebuild and install the native changes:

```sh
cd ~/workspace/yuke
mise exec -- python3 tools/package.py --nightly
python3 ~/dotfiles/yuke-rust/scripts/install.py --source "$PWD" --archive target/packages/yuke-aarch64-macos.tar.gz --activate
```

The installer runs the profile and prepared-data checks before changing the default command.
Its prepared-data equality and zero-chat checks apply to the initial migration.
After normal Rust use starts, add `--update` to the installer command.
That option keeps the installed profile and skips the initial state copy and equality checks.

To restore the Zig default:

```sh
cp ~/.local/bin/yuke-zig ~/.local/bin/yuke
```

The old profile, chat store, SDK, and native executable stay available.
To use Rust again without changing the default, run `yuke-rust`.

## Plugin installation

The canonical plugin list is `~/dotfiles/yuke-rust/.config/yuke-rust/config.json`.
The running profile reads `~/.config/yuke-rust/config.json`.
A string such as `"./plugins/dashboard"` loads a local folder relative to that config file.
An object with `path` can also supply `options`.
Each folder's `plugin.json` names its entry under `extensions["sh.yuke"].entry`.

A Git-managed plugin uses a repository URL and a folder:

```json
{
  "git": "https://github.com/lostcoords/yuke-plugins",
  "folder": "plugins/btw",
  "ref": "main"
}
```

`plugins.lock` records the exact commit.
`yuke plugin add URL --folder plugins/btw` adds and installs that plugin.
`yuke plugin sync --locked` restores the locked versions.
`yuke plugin update --all` checks for updates and asks before changing the lock.
The `/plugins` dialog manages the same entries.
Run `/reload` while idle after a plugin change.
Keep the canonical dotfiles config and lock in sync with changes made through the manager.

The latest upstream plugin checkout is `~/workspace/yuke-rust-plugins-upstream`, at `b1ce90628344437c1a2bc8b45b9e6119b21f95f8`.
It provides `vim`, `subagents`, `btw`, and `mailbox`.
The current personal profile keeps its 26 customized plugins local.
Upstream Vim provides composer editing and does not provide the personal transcript navigation.
Upstream subagents does not include the personal roles and campaign policy.
Replacing those custom folders with stock packages removes those additions.
The new mailbox requires upstream's newer Unix listener API, which this installed native base does not contain.
Fetching the source does not enable that plugin.
