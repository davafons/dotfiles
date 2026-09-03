---
description: Split the current jj revset into smaller commits grouped by feature/area, ready to push
---

Split all uncommitted changes in the current **jj** working-copy commit (`@`) into
several smaller commits, each grouping the files that belong to one feature or
logical area, so they can be pushed to `main` later.

Optional guidance from the user on how to group: $ARGUMENTS

## Rules

- Use **jj**, never git.
- Group **by file** — never split a single file's content across commits. Every
  changed file lands wholesale in exactly one commit.
- Tests, linting, and builds do **not** need to pass — this is purely
  organizational. Do not run tests, formatters, or builds.
- Do **not** push, and do not create bookmarks/branches. Just leave a clean stack
  on top of `main`.
- These are the user's own working changes — write plain descriptive messages, and
  do **not** add a Co-Authored-By trailer.

## Steps

1. List what changed: `jj diff -r @ --name-only`.
2. Decide logical groups. Cluster by feature/area, keeping each feature's source,
   tests, and docs/specs together. Aim for a handful of coherent commits, not
   one-per-file, with a final **Chore** catch-all for shared files.
3. For every group **except the last**, run:

   ```
   jj split -m "<Feature>: <concise summary>" <path> <path> ...
   ```

   Passing filesets makes the split non-interactive. Never invoke `jj split`
   without filesets. Directory paths match recursively; list individual files
   otherwise.
4. Whatever is left in `@` is the final group — name it with:
   `jj describe -m "<summary>"`.
5. Show the result:

   ```
   jj log -r 'trunk()::@' --no-graph -T 'if(current_working_copy, "@ ", "  ") ++ description.first_line() ++ "  [" ++ diff.files().len() ++ " files]\n"'
   ```

## Notes

- `jj undo` reverses the last operation; `jj op log` shows operation history.
- If a split matches no files, correct the path and retry that group.
- Report the final stack with commit titles and file counts; do not paste full diffs.
