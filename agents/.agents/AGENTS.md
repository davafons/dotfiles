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

The **mutating** rows above (`describe`, `new`, `squash`, `rebase`, `bookmark`, `push`) are
the right translation *when I have asked you to do that operation*. Unasked, they are off
limits — see the next section.

## The working copy is shared with other agents

Several agents work in the same checkout at the same time, on the same revset. **A dirty
working copy full of someone else's changes is the normal, expected state** — it is not a
problem to clean up and not a reason to stop.

- **Do not restructure the revset.** No `jj split`, no `jj new`, no `jj rebase`, no
  `jj squash`, no `jj abandon`, no moving bookmarks. Any of these yank the working copy out
  from under whoever else is mid-edit.
- **Do not `jj describe` the working copy** to claim your work: `@` holds everyone's
  changes, so a message describing only yours mislabels theirs (this once swept ~2,100 lines
  of unrelated work onto main).
- **Just edit the files you were asked to edit and leave them.** Committing and organising
  the revset is the human's job unless they explicitly ask you for it.
- Read-only inspection is always fine: `jj st`, `jj log`, `jj diff --git`, `jj show`.
- If you genuinely need work isolated, ask — do not isolate it yourself.

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
