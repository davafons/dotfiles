---
name: split-revset
description: Split the current jj working-copy revset into smaller feature-grouped commits, ready to push later. Use when the user asks to split or organize a jj revset; do not push or create bookmarks.
argument-hint: "[optional grouping guidance]"
---

# Split Revset

Split all changes in the current **jj** working-copy commit (`@`) into several smaller
commits, grouping files by feature or logical area.

Optional grouping guidance from the user: `$ARGUMENTS`

## When to use

Use for organizational cleanup of a user's current jj working-copy revset. This skill does
not push, create bookmarks or branches, run tests, or split the contents of a single file.

## Constraints

- Use **jj**, never git.
- Group **by file**. Every changed file lands wholesale in exactly one commit.
- Tests, linting, and builds do not need to pass; do not run them.
- Do not push or create bookmarks/branches. Leave a clean stack on top of `main`.
- Use plain descriptive commit messages without a `Co-Authored-By` trailer.

## Procedure

1. Check the changed files with `jj diff -r @ --name-only`.
2. Cluster files into a handful of coherent groups by feature/area, keeping each feature's
   source, tests, and docs together. Useful axes include top-level app areas, deploy/ops,
   openapi, audio, tokenizer/search, SRS/cards, and sentence-mining. Use a final `Chore:`
   catch-all for genuinely shared or stray files.
3. For every group except the last, run:

   ```
   jj split -m "<Feature>: <concise summary>" <path> <path> ...
   ```

   Pass filesets so the split is non-interactive. Never invoke `jj split` without filesets.
   Directory paths match recursively. The selected paths become a described commit and the
   remaining changes move into a new child that becomes `@`; continue operating on `@`.
4. Describe whatever remains in `@` as the final group:

   ```
   jj describe -m "<summary>"
   ```

5. Show the resulting stack:

   ```
   jj log -r 'trunk()::@' --no-graph -T 'if(current_working_copy, "@ ", "  ") ++ description.first_line() ++ "  [" ++ diff.files().len() ++ " files]\n"'
   ```

## Pitfalls and recovery

- If a split matches no files, correct the path and retry; earlier splits are unaffected.
- If an operation must be unwound, `jj undo` reverses the last operation and `jj op log`
  shows the operation history.

## Verification

- Every original changed file appears in exactly one resulting commit.
- Each commit has a concise descriptive message.
- The final `jj log` output shows the complete stack and file counts.
- No push, bookmark, branch creation, tests, formatters, or builds were run.
