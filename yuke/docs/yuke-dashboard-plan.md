# Export the Yuke dashboard

People who install the plugin get an empty-session menu without Vim. The menu shows sign-in, the model picker, and commands, then adds commands other plugins register. A profile settings file can replace labels, keys, order, and membership. The changes are `yuke-plugins-dashboard`, then `dotfiles-dashboard-pin`.

## How to read this

One box is one unit of work. Every box names the evidence that checks it. A nested box is a sub-step of the box above it. Check a box only when its evidence exists, a file, a log line, a screenshot, a test run, or a SHA. The body is a how-to. The appendices explain and record.

The program is an operator checklist. It does not run `playbooks/autopilot-full.md`, `playbooks/autopilot-stack.md`, or `playbooks/orchestrate.md`. Those workflows merge a queue or run a standing program. No merge grant exists here. The operator lands both changes after review. Start execution only on an explicit go.

Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

## Program checklist

### Arm the program

- [ ] State the protocol and this plan to the operator, then stop. Start execution only on the operator's explicit go.
- [ ] Read the project-owned workflows from current trunk at program start. In a jj repository use `jj file show -r main <project workflow path>`. Read the installed or pinned canonical source for external protocols. Re-read them at every tick.
  - [ ] Read `~/.agents/skills/dav-mode/playbooks/multi-phase-plan.md`.
  - [ ] Read the [swarm protocol](https://github.com/cursor/plugins/blob/1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def/pstack/skills/swarm/SKILL.md) and the runtime delegation rules in `~/.agents/skills/dav-mode/references/playbook-runtime.md`.
  - [ ] Read `~/.agents/skills/control-cli/SKILL.md` and `yuke/tests/check-profile.py` for the private PTY driver.
  - [ ] Read the PR handoff in `~/.agents/skills/dav-mode/references/playbook-runtime.md` and the project's approved PR workflow.
  - [ ] Read `~/.local/lib/yuke/docs/ui.md` and `~/.local/lib/yuke/docs/plugins.md` before editing the plugin.
- [ ] On the operator's go, arm `/loop 1h` with the tick prompt below through the installed loop skill and the runtime's available, authorized scheduler. Record the loop ID and lifetime. In Yuke, quit or profile reload stops the loop and requires explicit rearming. Never leave the cadence to memory. If no native scheduler is available, report the gap and leave automatic execution unarmed. Do not arm the loop for this two-change extract unless the operator asks for a standing run.
- [ ] Use this tick prompt, verbatim. "Re-read project-owned execution instructions from trunk and external playbooks from their installed or pinned canonical source. Audit the operation against those instructions and fix drift in this tick. Probe every active lane and judge progress by side effects only. Stand down a stuck lane and dispatch its replacement now. Then post a short status message to the operator in chat only when the audit found a tracked change that no earlier status message reported, such as a PR opened, a code-ready head, a round launched or closed, a verdict, a merge, a stuck agent and the action taken, a blocker added or cleared, or a decision only the operator can make. Name every such change and nothing else. Do not repeat a table, the merged list, or an unchanged blocker. If the audit found none, end the turn with no reply text. Either way, log this tick's row in your decision trail. The row names the items reported, or none."
- [ ] On the operator's hold or stand-down, send every owner a zero-writes order at once.

### Spawn owners

- [ ] Spawn one owner per PR with the full lifecycle the execution playbook names. Delegation still needs an explicit go. Until then the operator runs the boxes directly.
- [ ] Follow this dependency graph. Start dependent work only after its parent merges, or base it on the parent branch when the execution playbook stacks.
  - [ ] `yuke-plugins-dashboard` is first. Branch it from `yuke-plugins` `main`, not from `davafons/solarized-theme`.
  - [ ] `dotfiles-dashboard-pin` after `yuke-plugins-dashboard` has a commit SHA to pin.
- [ ] Hold the file boundaries. `yuke-plugins-dashboard` touches only `plugins/yuke-dashboard/**`. `dotfiles-dashboard-pin` touches only the profile config, the dashboard settings file, the local dashboard folder, and the profile changelog notes.
- [ ] Hold the review gate. Both changes alter the empty-session interaction. They wait for the operator's review in chat with screenshots and a video before merge.

### PR mechanics, for every PR

- [ ] Resolve the forge once. Default to `gh`; if `command -v origin` succeeds and Origin can resolve the repository, use `origin pr` for every PR operation. Record any fallback to `gh`. Never require `gt`.
- [ ] Open the PR ready, never draft, per the PR handoff in `~/.agents/skills/dav-mode/references/playbook-runtime.md`. Use the run's built-in PR tool when it has one, else `origin pr create --status open --base <base-branch>` or `gh pr create --base <base-branch>` according to the resolved forge. A stack child targets its parent branch. Do not open or push until the operator's go.
- [ ] Run the repo's lint and typecheck once before the PR-facing push. Push through the project's approved formatter, lint, and pre-push workflow; do not assume Git hooks run in jj.
- [ ] Run the project's code-quality checks before each scoped change and the no-comments skill at `~/.agents/skills/no-comments/SKILL.md` before review.
- [ ] Triage every automated code/security-review comment against the source and evidence. Fix real defects, dismiss non-issues with a concrete reason, and ask only for decisions the operator must make.
- [ ] Rebase onto current trunk before the code-ready report and PR-status driving. Keep that merge base in fix rounds. Rebase again only at merge prep, on a native conflict check with trunk, or on a CI failure that comes from a change on trunk.

### Verdict and merge, for every PR

- [ ] At the code-ready head SHA and at each later push that changes the patch, run the coverage matrix per the [swarm protocol](https://github.com/cursor/plugins/blob/1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def/pstack/skills/swarm/SKILL.md) through authorized native agents. One gates lane. The ten live lanes from the PR's **Verify, live** block. The perf lane from its **Verify, perf** block. Two or more audit lanes, each with its own focus, that read the diff and the receipts and distrust the PR body. The root audits the receipts in the merge-ready report before the verdict.
- [ ] Clean only when every lane is `PASS`. Findings go back to the owner, including a defect that a lane filed as a note. A new head gets a fresh coverage run and a fresh verdict, except for results that stay valid under the patch-id rule in `~/.agents/skills/dav-mode/playbooks/shipping.md`.
- [ ] The operator lands each change. No owner merges, pushes a shared bookmark, or updates the active profile without that go. Apply the patch-id rule from `~/.agents/skills/dav-mode/playbooks/shipping.md` before treating an old receipt as still valid.

### Boot recipe, for every live lane

Each live lane runs in its own available isolated test environment at the exact PR head. Drive through the project's matching verification/control workflow.

- [ ] Fetch the head through native version control, then create or select the lane's isolated checkout at the head SHA. In jj use `jj git fetch` and `jj new <head SHA>` inside that lane's own workspace, not the user's active checkout.
- [ ] Start Yuke with a private `HOME`, `XDG_CONFIG_HOME`, `XDG_DATA_HOME`, and `XDG_STATE_HOME`. Load only the plugins that lane names. Do not copy provider credentials. Do not call a model.
- [ ] Deliver keys with `root.onEvent` inside an isolated plugin, or with the private PTY pattern in `yuke/tests/check-profile.py`. Do not activate the user's terminal or send system-wide input.
- [ ] Save every screenshot to `/tmp/swarm-<pr-id>/worker-<n>/<slug>.png` and return the paths with the report.

## Add the dashboard plugin (yuke-plugins-dashboard)

**Depends on.** None.

**Files.**

- [ ] Create the workspace `/Users/davafons/workspace/yuke-plugins-dashboard` from `yuke-plugins` `main` with `jj workspace add --name yuke-dashboard -r main`.
- [ ] Create `plugins/yuke-dashboard/plugin.json`.
- [ ] Create `plugins/yuke-dashboard/index.js`.
- [ ] Create `plugins/yuke-dashboard/menu.js`.
- [ ] Create `plugins/yuke-dashboard/settings.js`.
- [ ] Create `plugins/yuke-dashboard/README.md`.
- [ ] Create `plugins/yuke-dashboard/tests/menu.test.js`.
- [ ] Do not edit `plugins/vim-mode/**` or the solarized bookmark.

**Build.**

- [ ] Declare `uses` as `tui` only. Do not require `composer-vim`.
- [ ] Put menu resolution in `resolveMenu` in `menu.js`. Defaults are `auth:login`, `model:pick`, `ui:palette`, `ui:sessions`, and `quit`, each only while `command.available` is true. `ui:palette` has no `desc`, so it comes from this default list, not from `command.list`.
- [ ] Append described commands whose `command.map` owner is not `core`, unless settings hide them or `includeRegistered` is false. Refresh on `ui.started` and by advising `Object.getPrototypeOf(tui.command).add`, because an apply-time `list` misses plugins that load later.
- [ ] Read `yuke-dashboard.json` from the profile directory, not from `ctx.root`. The GitHub cache is replaced when `ref` changes.
- [ ] When that file is absent, show the defaults plus registered plugin commands, with no letter keys.
- [ ] When the file sets `actions`, that array is the menu order. Optional `label` and `key` override the command text and shortcut. A missing command is omitted and reported. A duplicate key leaves the later row without a key and is reported.
- [ ] Intercept an assigned key with around-advice on `ChatView.prototype.onKey` only while the pane is an empty unsaved chat. That key runs the command and does not insert. Any other character calls the original handler and inserts.
- [ ] Keep mouse selection on `chat.press`. Do not advise the keymap for plain letters. A keymap-first route swallows keys the composer must still receive.
- [ ] If `composer-vim` is present and the settings file assigns no keys, bind the five default commands to `l`, `m`, `c`, `r`, and `q` only while Vim is in normal mode on that empty chat. Insert mode still types. Do not hardcode `search:open` or `project-work:work`.

**You see.**

- [ ] An isolated check with no Vim plugin prints a menu that includes sign-in, the model command, and commands, and includes a command registered by a later plugin.
- [ ] The same check shows an action key leaving the composer empty, and a different letter inserted into the composer.
- [ ] The README names the GitHub source entry and the settings file path.

**Verify, unit.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] `plugins/yuke-dashboard/tests/menu.test.js` covers defaults, a command with no description, a later plugin owner, a hidden name, a full `actions` replacement, and a duplicate key. Run `node plugins/yuke-dashboard/tests/menu.test.js` from the dashboard workspace.

**Verify, live.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. Ten lanes on `openai-codex/gpt-6.1-sol` at the PR head, per the boot recipe.

- [ ] Lane 1. Regression lane against trunk. Run the empty-chat load at `yuke-plugins` `main` and at the head. Trunk has no dashboard. Record that, and gate the added empty menu plus the end state the user waits for, which is a visible sign-in row and a typed letter in the composer. Save `/tmp/swarm-yuke-plugins-dashboard/worker-1/regression.png`. Pass when trunk has no dashboard row and head shows sign-in after the letter `x` is inserted.
- [ ] Lane 2. Stock profile, no Vim, no settings file. Save `/tmp/swarm-yuke-plugins-dashboard/worker-2/defaults.png`. Pass when the screen shows sign-in, the model row, and commands, and `ui:palette` runs from the commands row.
- [ ] Lane 3. A later plugin registers `later:open` with a description. Save `/tmp/swarm-yuke-plugins-dashboard/worker-3/later.png`. Pass when that row appears without a hardcoded name in the dashboard defaults.
- [ ] Lane 4. Settings `actions` lists only `quit`. Save `/tmp/swarm-yuke-plugins-dashboard/worker-4/custom-order.png`. Pass when quit is the only default row and a registered plugin command still appears because `includeRegistered` stays true.
- [ ] Lane 5. Settings hide `auth:login` and set `includeRegistered` false. Save `/tmp/swarm-yuke-plugins-dashboard/worker-5/hidden.png`. Pass when sign-in is absent and the later plugin row is absent.
- [ ] Lane 6. Settings assign `l` to `auth:login`. Save `/tmp/swarm-yuke-plugins-dashboard/worker-6/key.png`. Pass when `l` runs login and leaves the composer empty, and `x` inserts `x`.
- [ ] Lane 7. Vim is loaded and the settings file assigns no keys. Save `/tmp/swarm-yuke-plugins-dashboard/worker-7/vim-normal.png`. Pass when normal-mode `m` runs the model command and insert-mode `m` inserts `m`.
- [ ] Lane 8. Click the commands row. Save `/tmp/swarm-yuke-plugins-dashboard/worker-8/click.png`. Pass when `ui:palette` runs and the composer text stays empty.
- [ ] Lane 9. Settings name a missing command and use a two-character key. Save `/tmp/swarm-yuke-plugins-dashboard/worker-9/bad-settings.png`. Pass when the dashboard still loads, the bad row is omitted, and the report names both faults.
- [ ] Lane 10. Narrow pane under 40 columns, then reload. Save `/tmp/swarm-yuke-plugins-dashboard/worker-10/narrow-reload.png`. Pass when the menu remains readable, the settings file is still applied, and a removed plugin command is gone.

**Verify, perf.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] Metric. Time to resolve a menu of 40 described commands, plus the empty-screen end state the user waits for. Trunk has no dashboard, so also record trunk `command.list` duration and do not treat that as the same scenario.
- [ ] Probe. In the isolated check, time `resolveMenu` for 40 fixture commands at trunk and at the head, interleaved, after a warm-up call. Both sides must print a millisecond value. Head must also print the visible default row names.
- [ ] Baseline. Record the trunk `command.list` milliseconds first.
- [ ] Rule. Fail the head when `resolveMenu` takes 5 milliseconds or more, or when the visible rows omit sign-in or commands. Do not report a ratio against trunk `command.list`.

**Review gate.** The operator reviews before merge.

- [ ] Copy lane 2 and lane 6 screenshots into `/tmp/swarm-yuke-plugins-dashboard/review-defaults.png` and `/tmp/swarm-yuke-plugins-dashboard/review-key.png`.
- [ ] Record a 30 to 60 second video of the empty menu, one action key, and one typed letter in a lane's isolated test environment. Save it as `/tmp/swarm-yuke-plugins-dashboard/review.mp4`.
- [ ] Post the screenshots and the video in chat. Stop at merge-ready. Wait for the operator's click.

**Merge.**

- [ ] Root's clean verdict at the exact head SHA.
- [ ] Automated code and security review triage done.
- [ ] Rebased onto current `yuke-plugins` `main` after the verdict, patch-id unchanged.
- [ ] The operator sets bookmark `davafons/yuke-dashboard` on that commit. No owner pushes or merges it.

## Pin the profile to the published dashboard (dotfiles-dashboard-pin)

**Depends on.** `yuke-plugins-dashboard`.

**Files.**

- [ ] Edit `yuke/.config/yuke/config.json`.
- [ ] Create `yuke/.config/yuke/yuke-dashboard.json`.
- [ ] Delete `yuke/.config/yuke/plugins/yuke-dashboard/`.
- [ ] Edit `yuke/CHANGELOG.md` and `yuke/README.md` only where they name the local dashboard folder.

**Build.**

- [ ] Replace the local `./plugins/yuke-dashboard` entry with a GitHub source for `lostcoords/yuke-plugins`, path `plugins/yuke-dashboard`, and `ref` set to the full commit from `yuke-plugins-dashboard`.
- [ ] Write `yuke-dashboard.json` with the current personal keys `r`, `s`, `w`, `m`, `c`, and `q` for `ui:sessions`, `search:open`, `project-work:work`, `model:pick`, `ui:palette`, and `quit`. Set `includeRegistered` true so later plugin commands still appear.
- [ ] Leave the local Vim plugin in place. Do not publish it.

**You see.**

- [ ] The profile config no longer lists a local dashboard folder.
- [ ] An isolated copy of the profile loads the pinned commit and still shows the personal key rows.

**Verify, unit.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] A profile JSON check asserts the GitHub entry, the full commit, and the six personal keys. Run that check from the dotfiles root and keep the command in the change notes.

**Verify, live.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. Ten lanes on `openai-codex/gpt-6.1-sol` at the PR head, per the boot recipe.

- [ ] Lane 1. Regression lane against trunk. Run the empty-chat key `s` at the current local dashboard and at the pinned profile. Save `/tmp/swarm-dotfiles-dashboard-pin/worker-1/regression.png`. Pass when both open search and neither inserts `s` while Vim is in normal mode.
- [ ] Lane 2. Isolated profile with the pin and no local dashboard folder. Save `/tmp/swarm-dotfiles-dashboard-pin/worker-2/pin.png`. Pass when the loaded plugin root is the cache snapshot for the pinned commit.
- [ ] Lane 3. Personal key `w` with project work loaded. Save `/tmp/swarm-dotfiles-dashboard-pin/worker-3/work-key.png`. Pass when `project-work:work` runs and the composer stays empty.
- [ ] Lane 4. Remove the project-work plugin and reload. Save `/tmp/swarm-dotfiles-dashboard-pin/worker-4/missing-work.png`. Pass when the work row is omitted, the fault is reported, and the other personal rows remain.
- [ ] Lane 5. Type `x` in insert mode. Save `/tmp/swarm-dotfiles-dashboard-pin/worker-5/insert.png`. Pass when the composer text is `x` and no action runs.
- [ ] Lane 6. Click Resume. Save `/tmp/swarm-dotfiles-dashboard-pin/worker-6/click-resume.png`. Pass when `ui:sessions` runs.
- [ ] Lane 7. A plugin registered after the dashboard adds a described command. Save `/tmp/swarm-dotfiles-dashboard-pin/worker-7/extra.png`. Pass when that row appears below the personal six.
- [ ] Lane 8. Reload after saving a draft. Save `/tmp/swarm-dotfiles-dashboard-pin/worker-8/reload.png`. Pass when the documented reload warning still applies and the menu returns on the next empty chat.
- [ ] Lane 9. Point `ref` at a missing commit in a disposable copy. Save `/tmp/swarm-dotfiles-dashboard-pin/worker-9/bad-ref.png`. Pass when that copy reports a source failure and does not delete the settings file.
- [ ] Lane 10. Confirm the active user profile was not modified by the lane. Save `/tmp/swarm-dotfiles-dashboard-pin/worker-10/untouched.png`. Pass when the lane used a private home and the user's `config.json` mtime is unchanged.

**Verify, perf.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] Metric. Isolated `yuke check` duration for the profile, plus the empty-menu end state the user waits for. Trunk is the local dashboard folder. Head is the pinned snapshot.
- [ ] Probe. Run the same isolated check at trunk and head, interleaved, three times each. Record the wall time and the menu row names.
- [ ] Baseline. Record the trunk median seconds first.
- [ ] Rule. Fail when the head median exceeds the trunk median by 1 second or more, or when the head menu omits the personal Resume row. Both sides must reach an empty menu.

**Review gate.** The operator reviews before merge.

- [ ] Copy lane 1 and lane 2 screenshots into `/tmp/swarm-dotfiles-dashboard-pin/review-regression.png` and `/tmp/swarm-dotfiles-dashboard-pin/review-pin.png`.
- [ ] Record a 30 to 60 second video of the pinned empty menu and one personal key. Save it as `/tmp/swarm-dotfiles-dashboard-pin/review.mp4`.
- [ ] Post the screenshots and the video in chat. Stop at merge-ready. Wait for the operator's click. Do not copy the pin into the active profile until that click.

**Merge.**

- [ ] Root's clean verdict at the exact head SHA.
- [ ] Automated code and security review triage done.
- [ ] Rebased onto current dotfiles `main` after the verdict, patch-id unchanged. Preserve unrelated working-copy edits.
- [ ] The operator lands the local commit. No owner pushes it.

## Close the program

- [ ] Every box above is checked with its evidence.
- [ ] Reply to the operator with the two head SHAs, the bookmark name, and the review still waiting. Do not claim the active profile changed.

## Appendix A. Prototype evidence

The throwaway probe lives at `/tmp/yuke-dashboard-proto.DsrwAy`. It is not the plugin. An isolated `yuke check` loaded `dash-probe` before `later` and dispatched keys with `root.onEvent`. No Vim plugin was loaded.

```
pane=chat
palette=true
login=true
model=true
sessions=true
afterL text="" ran=1
afterX text="x" ran=1
```

`command.list` during `dash-probe` apply included `auth:login`, `model:pick`, and `ui:sessions`. It did not include `ui:palette` or `later:open`. Advising `Object.getPrototypeOf(tui.command).add` then recorded `later:open`. `ui.started` did not fire in `yuke check`, so the live lanes still have to prove the painted screen and the startup refresh.

A keymap-first route was not prototyped. The installed UI guide says a plain letter reaches the keymap only through `tui.route.add`, and the dispatcher skips the view when that route matches. That would block typing. The chosen path is `ChatView` advice, which the probe already observed.

## Appendix B. Alternatives rejected

A copied local dashboard stays tied to `composer-vim` and to personal command names. That fails the request that the plugin work without Vim.

A keymap-first route can steal letters, but it also swallows every other key. The user could not start a prompt.

An in-dashboard editor is a second interaction. The settings file already expresses order, labels, keys, hiding, and whether registered commands are added. An editor can write that same file later.

Putting settings in `ctx.root` loses them when a GitHub snapshot is replaced. The profile file survives a `ref` change.

Publishing the personal Vim plugin is out. Its composer snapshot calls are not on upstream `main` at `f9303882`.

Basing the worktree on `davafons/solarized-theme` would mix the theme into the dashboard branch. The dashboard branch starts at `main`.

## Appendix C. Risks

`yuke-plugins-dashboard` paints through a private PTY. A PNG and an mp4 recorder are not proven in that driver. The lanes still name the files. The review gate stays open until those artifacts exist. Do not treat `root.onEvent` text as a screenshot.

`dotfiles-dashboard-pin` must not edit the active profile during a lane. Lane 10 watches the user config mtime.

A settings command that loads later must not be rejected during dashboard apply. Resolve names again on `ui.started` and on advised `add`.

`includeRegistered` can show two rows for one task, such as core `ui:sessions` and a plugin `resume` alias. The settings file can hide one. Do not guess which alias is redundant.

## Appendix D. Links and reading list

Read `~/.local/lib/yuke/docs/ui.md` for keys, routes, and commands. Read `~/.local/lib/yuke/docs/plugins.md` for advice and `ctx.root`. Read `~/.local/lib/yuke/docs/profile.md` for GitHub sources and the isolated check. Read the solarized install note at `davafons/solarized-theme` in `yuke-plugins` before writing the dashboard README.

The decision trail for execution belongs outside the jj snapshot. This plan does not start that trail. No how or interrogate pass is required before the operator's go. The prototype already settled the key and registry questions.
