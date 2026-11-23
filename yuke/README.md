# yuke

Fresh profile for yuke. Stow links `.config/yuke` into `~/.config/yuke`.

It runs a local build of yuke: upstream main plus my open pull requests, installed by the official installer to `~/.local/bin/yuke` and `~/.local/lib/yuke`.
Do not run `yuke update`. It installs the official nightly, which lacks those pull requests, and the profile then fails to load (`bundled.chat.favorites` is an unknown option there).
It loads upstream plugins from `lostcoords/yuke-plugins` as Git entries pinned in `plugins.lock`.
After a changed `plugins.lock`, run `yuke plugin sync --locked`.

The old profile stays in `../yuke-rust` and still runs as `yuke-rust` on the native release of `davafons/rust-plugins`.
Each plugin came back here only after a review. Every row of the tracker below is done. Delete `yuke-rust` after the open pull requests merge.

## Local build

The checkout is `~/workspace/yuke` (jj). The bookmark `davafons/local` is a merge of `main@origin` and each open pull request branch:

| Pull request | Bookmark | Replaces |
| --- | --- | --- |
| lostcoords/yuke#16 | `davafons/system-prompt` | the `personal` plugin: yuke reads `SYSTEM.md` |
| lostcoords/yuke#17 | `davafons/model-favorites` | the `models` plugin: `bundled.chat.favorites` |
| lostcoords/yuke#18 | `davafons/path-completion` | the `path-completion` plugin: `@~/`, `@../`, and `@/absolute` paths complete |
| lostcoords/yuke#19 | `davafons/ctrl-c-quit` | the layered Ctrl+C of `controls`: a second ctrl+c in an empty draft quits |
| lostcoords/yuke#20 | `davafons/thought-durations` | the thought times of `run-feedback`: a saved thought shows `Thought · 8s` |
| lostcoords/yuke#21 | `davafons/session-record` | `SessionHandle.record`: `!command` saves its output with no model turn |
| lostcoords/yuke#22 | `davafons/process-spawn` | `Command.spawn`: piped stdin and streamed output, for `!command` and `sudo -S` |
| lostcoords/yuke#23 | `davafons/optional-services` | `optionalUses` and `ctx.find`: `usage` adds `u` to the dashboard menu without a need for the dashboard |

Rebuild after a pull request changes, after upstream main moves, or after a merge:

```sh
cd ~/workspace/yuke
jj git fetch --remote origin
# Each open pull request branch rebases onto upstream main. Drop a branch from the merge after its pull request merges.
jj rebase -b davafons/system-prompt -b davafons/model-favorites -b davafons/path-completion -b davafons/ctrl-c-quit -b davafons/thought-durations -b davafons/session-record -b davafons/process-spawn -b davafons/optional-services -o main@origin
jj new main@origin davafons/system-prompt davafons/model-favorites davafons/path-completion davafons/ctrl-c-quit davafons/thought-durations davafons/session-record davafons/process-spawn davafons/optional-services -m "local: yuke main with my open pull requests"
# #20 and #21 meet in one test: the merge passes `&[]` as the new durations argument at `crates/engine/src/turn_state/tests.rs` (the record test).
jj bookmark set davafons/local -r @ --allow-backwards
jj new davafons/local          # Git HEAD must be the merge, so the package names its commit and is not dirty
mise run check
mise exec -- python3 tools/package.py --nightly
bash tools/install.sh target/packages/yuke-aarch64-macos.tar.gz
```

When every pull request has merged and shipped in the nightly, go back to the official build with `yuke update`.

## Live state

| Path | Contents |
| --- | --- |
| `~/.config/yuke/tsconfig.json` | Written by the installer |
| `~/.local/share/yuke/auth.json` | Logins, copied from `yuke-rust` on 2026-11-22 |
| `~/.local/share/yuke/sessions*` | Chat store. Old chats stay in `~/.local/share/yuke-rust` |

## Port tracker

For each plugin, check upstream yuke and `yuke-plugins` first. Then pick one result:

- **upstream**: yuke or `yuke-plugins` already does it. Load that, or drop the plugin.
- **contribute**: generic. Move it to a branch in `~/workspace/yuke-plugins` (or yuke for a core API) and open a PR.
- **personal**: keep it in `.config/yuke/plugins/`.
- **drop**: not used.

| Done | Plugin or feature | Result | Notes |
| --- | --- | --- | --- |
| ✓ | vim | upstream | Loaded from `yuke-plugins` branch `davafons/vim-ctrl-c` (PR #4) until it merges; then set `ref` back to `main`. Dropped (not needed): transcript motions and the mode service (draft PR yuke-plugins#1, closed) |
| ✓ | btw | upstream | Loaded from `yuke-plugins` |
| ✓ | subagents | upstream | Loaded from `yuke-plugins`. Compare with agent-tools |
| ✓ | titles | upstream | Loaded from `yuke-plugins`. Models in `~/.local/share/yuke/plugins/titles/settings.json`: `claude-bridge/haiku`, then `openai-codex/gpt-5.6-luna` (low) |
| ✓ | mailbox | upstream | Loaded from `yuke-plugins`. Overlaps herdr and project-work messages |
| ✓ | providers: `input`, `output`, `tools` model fields | drop | Not needed. Stock reads none of these fields to gate a request: a custom model gets images (checked with a fake provider: the request carries the `image` block). `catalog/list` only reports `input` |
| ✓ | models | contribute | PR lostcoords/yuke#17 (in the local build): aliases are `bundled.chat.favorites` in `config.json`; `/model` lists them first, each has `/<name>` and an optional key, `*` takes the newest version. Plugin deleted. Dropped: startup model (stock saves the last choice), effort picker, alias editor |
| ✓ | navigation | drop | Glue only: the `personal-navigation` service (`openSession` with a Herdr fallback, `openFile` in Herdr Code). Used by herdr, search, sessions-reworked. Fold it into herdr if herdr returns; else stock `chat.show` is enough |
| ✓ | solarized-theme | contribute | Ported. Adds `solarized`; `/themes` saves the choice. Dropped `dialog.border` (gone in stock). PR lostcoords/yuke-plugins#3 (`themes/solarized`). Loaded from the PR branch `davafons/solarized-theme`. After the merge, set its `ref` to `main` |
| ✓ | prompt-history | upstream | Dropped. The composer browses this session's messages with `up`/`down` from an empty draft, with images. Lost: `/history` picker (`ctrl+x p`, contribute candidate), browsing over a draft, `ctrl+k`/`ctrl+j` in Normal mode, the "working <message>" row |
| ✓ | path-completion | upstream + contribute | Dropped. The bundled `files` plugin completes `@` paths in the session folder (fuzzy, Git-aware). PR lostcoords/yuke#18 (in the local build) adds `@./`, `@../`, `@~/`, and `@/absolute` paths outside the session folder. Bare paths without `@` stay off. Lost: folder-only lists for `/cd` (workspace) |
| ✓ | personal | contribute | The prompt is `.config/yuke/SYSTEM.md`, which yuke reads natively with PR lostcoords/yuke#16 (in the local build). Plugin deleted. Dropped the `personal-commands` slash dispatch: stock commands take a `slash:` name |
| ✓ | controls | contribute | Layered Ctrl+C: PR lostcoords/yuke#19 (second ctrl+c in an empty draft quits, in the local build) and PR lostcoords/yuke-plugins#4 (ctrl+c leaves Insert/Visual, vim loaded from `davafons/vim-ctrl-c`). Dropped: Ctrl+H/J/K/L pane focus (stock `ctrl+k h/j/k/l`), `/exit`, `/close`, `/clear` aliases (stock `/quit`, `/new`), `/panel` (stock `ctrl+k v/s/c`), `ctrl+x b` for btw (stock `ctrl+k b` works) |
| ✓ | workspace | drop | Not used. `/cd` forked the session into another folder through the native fork destination; `/pwd` showed the folder (the status bar shows it) |
| ✓ | session-fork | drop | Not used. A `fork_session` model tool over `sessions.fork` (stock), with a folder option that needed the native branch |
| ✓ | sessions-reworked | upstream | Dropped. Stock `/sessions` has the folder/every-folder scope (`tab`), state marks, model, age, and fuzzy filter. Lost (not needed): delete with `ctrl+d`, more than 100 rows, refresh, `/resume` alias, Herdr owner jump |
| ✓ | search | drop | Not used. `/search`: SQLite full-text search of chat text and workspace files through a Python helper, with preview and jump to the message or file |
| ✓ | peek | upstream | Dropped: btw (loaded) asks side questions about the session without messaging it. Lost: `/peek provider/model` to ask with another model |
| ✓ | loop | upstream | Dropped. Stock background jobs (`exec` with `background: true`) wake the session when a command such as `gh run watch` ends. Lost: polling on a timer for things without a watch command |
| ✓ | agent-tools | upstream | Dropped for upstream subagents (loaded). Lost: named roles (general luna/medium, dav-agent, reviewer sol/xhigh; contribute candidate for subagents), model receipt, campaign quotas (`DAVSTACK_CAMPAIGN`), tool names `spawn_agent`/`send_agent_input` (upstream: `spawn_subagent`/`message_subagent`) |
| ✓ | dollar-skills | contribute | PR lostcoords/yuke-plugins#5 (`plugins/skills`), loaded from branch `davafons/skills`; after the merge, set its `ref` to `main`. `$name` loads that SKILL.md with the message; `$` completes names. Dropped the Python helper and the vim Insert-mode check. Lost: skills in other plugins' `skills` folders (no host API) |
| ✓ | run-feedback | contribute | Reviewed: wrong tok/s (counted the wait before the first token), frozen timers in split panes, short thought times, and a transcript takeover. Rewritten as two PRs: lostcoords/yuke-plugins#6 (`plugins/speed`, correct tok/s, loaded from branch `davafons/speed`) and lostcoords/yuke#20 (native `Thought · 8s`, saved with the session, in the local build). Tool rows already show durations in stock. Dropped: the per-round phase line |
| ✓ | step-trace | drop | Not used. Debug tracing of tools and the event loop, off by default |
| ✓ | yuke-clarify | contribute | Rewritten on stock APIs: PR lostcoords/yuke-plugins#7 (`plugins/questions`), loaded from branch `davafons/questions`. `ask_user` queues questions without a wait, the bar counts them, `/questions` answers them in the stock question view, and Esc keeps them for later. Dropped: the Python store and the custom inbox. Lost: requests do not survive a restart |
| ✓ | web | upstream (xyaman) | Dropped for `web` of xyaman/dotfiles (Git entry, pinned in `plugins.lock`): same Monid/TinyFish tools, with tests, a 50 KiB cap that saves the full output to a file, async polling, and detailed errors. The key is `~/.local/share/yuke/monid.key`; the `yuke` function in `shell/.bashrc.d/51_functions.sh` passes it as `MONID_API_KEY` to yuke only. Candidate for yuke-plugins if xyaman agrees |
| ✓ | project-work | drop | Shared tasks with claims across checkouts, a SQLite store through Python helpers, Herdr presence, and read-only GitHub reads. Upstream mailbox covers messages between sessions, and the agent reads GitHub with `gh` |
| ✓ | herdr | upstream (xyaman) | Dropped for `herdr` of xyaman/dotfiles (Git entry): reports idle, working, and blocked over all open sessions, and releases the pane on exit. Checked in a Herdr pane. Lost: blocked after a failed turn, `resume_argv` and the title as pane metadata (PR candidate for xyaman), click a file reference to open it in Herdr Code (`david.code`, personal candidate), jump to the pane of a session (not used) |
| ✓ | build-status | upstream | Dropped: the empty chat pane of stock shows the version, and `yuke --version` prints it |
| ✓ | sudo-command | contribute | Generic plugin `shell` ([yuke-plugins#9](https://github.com/lostcoords/yuke-plugins/pull/9)) on two core PRs: lostcoords/yuke#21 (`SessionHandle.record`) and #22 (`Command.spawn`). `!command` saves its output with no model turn. `!sudo` takes literal arguments only. The tool `sudo_command` shows the exact arguments first. The password goes through `sudo -A -k` and a FIFO askpass: no Python helper, no cached credential, and never to stdin of the command |
| ✓ | dashboard | contribute | PR lostcoords/yuke-plugins#10 (`plugins/dashboard`), loaded from branch `davafons/dashboard`; after the merge, set its `ref` to `main`. A centered start screen over the stock empty view (icon, "yuke", "unleash your harness", folder, model, version) with one-key actions: `r` sessions, `m` model, `t` themes, `l` sign in, `c` commands, `q` quit. The service `dashboard` lets other plugins add a row with `addItem`; `usage` adds `u`. Keys work in a fresh empty draft before the first typed key, or in Vim Normal mode; `i` types a message. Dropped: search and project tasks (plugins dropped) |
| ✓ | insights | contribute | `/usage` as the generic plugin `usage` ([yuke-plugins#8](https://github.com/lostcoords/yuke-plugins/pull/8)). It reads the sessions through the session API, and prices answers with the catalog. Loaded from branch `davafons/usage-dashboard`: #8 plus one commit that adds `u` to the dashboard menu through `optionalUses` (needs lostcoords/yuke#23). Open its pull request after #8 and yuke#23 merge; until then stock yuke refuses the `optionalUses` field. Dropped: `/context` and `/status` (native inspection API), and the account allowance (a Python helper) |
