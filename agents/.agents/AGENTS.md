# Version control

Check for `.jj/` at the repository root before running version-control commands.
If present, use jj instead of Git, including in colocated repositories.
Never mutate Git there or fall back to Git because a jj command failed.
Use `jj diff --git` for diffs and `jj push` for authorized pushes.
Use Git only in repositories without `.jj/`.

Never add AI co-author trailers such as `Co-authored-by: Claude` to commit messages.
Never add AI attribution such as "Generated with Claude" to commit messages or pull request descriptions.

## Work with jj changes

- Run `jj --version` and use `jj help <command>` to check syntax when uncertain.
  The guidance below targets jj 0.47.1 or newer.
- Start with `jj status`, `jj log`, and `jj diff --git`. Inspect existing work
  before changing history. Most jj commands snapshot working files, including
  new non-ignored files. There is no staging step or need for a WIP commit.
- `@` is the working-copy commit. `@-` selects its parents. Prefer change IDs
  when referring to work across rewrites; commit IDs change on every rewrite.
  A divergent change has multiple commit IDs, so select its exact revision
  when a command needs one target.
- For a new task, use `jj new <base>`. Edit files normally, then use
  `jj describe -m "..."` to describe the current change. Use `jj new` to start
  the next change on top. Only describe changes that belong to the task.
- To revise an owned change, use `jj edit <change>` and edit its files.
  Descendants rebase automatically. Check the resulting graph and conflicts.
- Use `jj diff --git -r <change>` for a change's patch,
  `jj diff --git --from <base> --to <head>` to compare trees, and
  `jj file show -r <revision> <path>` to read an older file.
- Quote revsets. `A::B` selects commits on paths from A to B, inclusive;
  `A..B` selects ancestors of B excluding ancestors of A;
  `mutable()` selects commits outside the immutable set.
  Preview a revset with `jj log -r '<revset>'` before using it to rewrite history.

## Reshape only owned work

- Use `jj squash --from <source> --into <target> <paths>` to move selected
  file changes. Omit paths only when the whole patch belongs in the target.
  Use `jj split <paths> -m "..."` to separate file changes in `@`.
  For selected hunks, use `-i` only when an interactive editor is available.
- Use `jj absorb` to distribute changes from `@` into their mutable ancestors.
  Review the affected ancestors first. `jj absorb -i` selects hunks interactively.
- Use `jj rebase -r <change> -o <base>` to move selected changes, or
  `jj rebase -s <change> -o <base>` to move a change and its descendants.
  Both can rewrite other descendants to repair ancestry. Inspect the graph
  first and preserve other people's work. Avoid an unscoped `jj rebase`.
- Respect immutable history. Do not bypass it with `--ignore-immutable` to
  make a command succeed. Do not abandon, restore, or squash unrelated work.
- Conflicts are stored in commits; a successful rebase can leave conflicts.
  Inspect with `jj status` and `jj resolve --list`. Edit the conflict markers
  into resolved text, then run `jj status` and inspect the diff. There is no
  `--continue` step. `jj resolve --tool :editor` opens the configured editor.
- For divergent changes, inspect `jj log` and `jj evolog -r <revision>`.
  Use `jj converge -r '<revset>' --no-interactive` only for owned divergence.
  It may leave divergence unresolved or introduce file conflicts, so inspect
  the result even when the command succeeds.

## Publish through bookmarks

- Bookmarks point to changes; creating a child does not advance a bookmark.
  Inspect `jj bookmark list --all-remotes`, then set an owned bookmark with
  `jj bookmark set <name> -r <change>` before publishing it.
- Fetch with `jj git fetch --remote <remote>`. Refer to remote bookmarks as
  `<name>@<remote>`. Track an existing remote bookmark with
  `jj bookmark track <name>@<remote>` when local tracking is intended.
- For an authorized push, use
  `jj push --remote <remote> --bookmark <owned-bookmark> --dry-run`, inspect
  the proposed updates, then repeat without `--dry-run`.
  `jj push` is a local alias, not a built-in command. Inspect
  `jj config get aliases.push` before relying on it; it can run `jj fix` and
  modify commits even during a dry run. Check the resulting patch and rerun
  affected checks before the real push. Do not bypass the alias if it fails.
- Avoid broad pushes. `--all` includes tags, and tracked tags can be pushed by
  default. Do not use obsolete `--allow-new` or disable push validation to
  work around an error.

## Isolate work and recover mistakes

- When running concurrent agents, give each writer a separate workspace with
  `jj workspace add --name <name> -r <base> <path>`. Workspaces share history
  and bookmarks, so use distinct changes and bookmark names as well.
  Use `--colocate` only when that workspace needs a Git worktree.
  Run `jj workspace update-stale` in a workspace reported as stale.
- For checks across a stack, use
  `jj run -r '<owned-revset>' --ignore-changes -- <check-command>`.
  Each revision gets an isolated working copy. Without `--ignore-changes`,
  command edits rewrite commits and propagate to descendants. Do not use
  `--ignore-errors` when the exit status must prove all checks passed.
- Inspect `jj op log` and `jj op show <operation>` before recovery.
  Use `jj --at-op=<operation> log` to inspect an earlier repository state.
  Use `jj undo` only after checking that the operation belongs to this task.
  Do not override the cross-workspace undo guard or restore the whole repo
  to undo one owned edit in shared work.
- For inspection without snapshotting or updating the working copy, use
  `jj --ignore-working-copy ...`. Results can omit unsnapshotted file edits.
  `--no-integrate-operation` leaves generated operations unintegrated and
  does not prevent external effects such as pushes.

Consult the [official jj documentation](https://docs.jj-vcs.dev/latest/) for
revsets, templates, and commands beyond this workflow. The project's
[AI Agent Skills wiki](https://github.com/jj-vcs/jj/wiki/AI-Agent-Skills) links
to community-maintained skills; those are not first-party jj instructions.
