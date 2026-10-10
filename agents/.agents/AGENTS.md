# davstack

For multi-step software development work, read
`~/.agents/skills/dav-mode/SKILL.md` and use its matching playbook unless the
user opts out. Personal workflows live in davstack; repository AGENTS.md files
supply project-specific architecture, commands, and constraints. User and
runtime instructions take precedence. If davstack is unavailable, report the
missing skill and continue from the available project instructions.

# Shared desktop

The user may be typing in another app at any time. This applies to every project
and delegated agent, not only browser tests.

- Prefer APIs, CLIs and verified background interactions.
- Browser work through the configured `browser` skill is pre-authorized to
  attach, create or select tabs, and activate its visible browser. Stay inside
  the wrapper-owned session and tab group; never use David's tabs or system-wide
  mouse and keyboard input.
- For other native GUI automation, do not activate apps, switch workspaces, or
  send system-wide input without explicit permission for that run. Starting or
  reconnecting a native automation tool can take focus too; do not rely on
  restoring it afterward.
- Use AeroSpace workspace 10 for agent-owned test windows. Name new test windows
  `Agent Tests <task>` where supported. Leave regular user windows alone. Another
  workspace does not isolate keyboard input or make native GUI automation safe.
- Preserve the user's clipboard. Do not play test audio without permission for
  audible testing. Use saved artifacts when showing progress does not need a window.
- If native GUI work cannot run without interference, pause that action and
  continue safe work. Coordinate access only when needed, or use a separately
  authorized desktop session or VM. Pass this restriction to delegated agents.

# Version control: use jj, never git

Most of my repos are jj/git colocated (`.jj/` sits next to `.git/`). **Before running any
version-control command, check whether the repo root has a `.jj/` directory** (`jj root`
succeeds, or `ls -d .jj`). If it does, drive everything through `jj`. Only repos with no
`.jj/` get plain git.

This is not a style preference. Mutating a colocated repo with git — `git add`,
`git commit`, `git checkout`, `git rebase`, `git stash`, `git reset` — desyncs jj's view of
the working copy and leaves me untangling it by hand. Don't reach for git because a jj
command failed; ask instead.

## Use this, not that

| Instead of | Use |
| --- | --- |
| `git status` | `jj st` |
| `git log` | `jj log` |
| `git diff` | `jj diff --git` (`-r <rev>` for one change) — **always `--git`** |
| `git show <rev>` | `jj show <rev>` |
| `git add` | nothing — the working copy is already a commit |
| `git commit -m "..."` | `jj describe -m "..."`, then `jj new` to start the next change |
| `git commit --amend` | just keep editing `@`, or `jj squash` into the parent |
| `git checkout <branch>` | `jj new <bookmark>` (new work) / `jj edit <rev>` (revise existing) |
| `git rebase` | `jj rebase -d <dest>` |
| `git stash` | `jj new` — park the work as its own change |
| `git branch` | `jj bookmark list`, `jj bookmark set <name> -r @-` |
| `git fetch` / `git pull` | `jj git fetch` |
| `git push` | `jj push` (my alias) |

Read-only git plumbing is fine where jj has no equivalent (`git blame`, `gh` commands),
but prefer the jj command whenever one exists.

Use the mutating jj commands when they are needed to complete the requested work.
Follow the branch workflow below.

## Work on top of main

- Always start feature branches or change stacks on top of `main` and keep them
  rebased onto `main` as development continues.
- Use mutating jj commands, including rebase, describe, new, squash, split, and
  bookmark updates, when needed to complete the requested work. There is no blanket
  prohibition on restructuring the working revset.
- Preserve unrelated changes when other agents share a checkout. Coordinate edits
  and inspect the current state before changing history; do not discard others' work.
- Use an isolated checkout when it is useful for concurrent work or testing, not
  as a mandatory substitute for updating the user's active checkout.

## Things that trip agents up

- **There is no staging area.** `@` is a real commit that updates as files change. Nothing
  to `add`; "uncommitted changes" is not a state that exists.
- **Bookmarks don't move on their own.** After finishing a change, point the bookmark at it
  explicitly: `jj bookmark set <name> -r @-` (usually `@-`, since `@` is the empty change
  you're about to work in), then push.
- **Push through my aliases.** `jj push` = `jj fix` (format/lint every mutable commit) then
  `jj git push`. `jj gpush` = run `scripts/pre-push` if present, then push. Prefer these
  over raw `jj git push`; jj does not run git hooks.
- **Commit signing is deliberately disabled** (`commit.gpgsign = false`) because pinentry
  has no TTY in agent sessions. Don't re-enable it, don't pass `-S`, and don't work around
  a signing error by switching to git.
- **Splitting work**: `jj split` for one commit, or the `/split-revset` command to break the
  current revset into per-feature commits ready to push.
