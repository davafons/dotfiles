---
description: Split the current jj revset into smaller commits grouped by feature/area, ready to push
allowed-tools: Bash(jj:*)
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
2. Decide logical groups. Cluster by feature/area, keeping each feature's source +
   its tests + its docs/specs together. Useful axes:
   - top-level app areas — `extension`, deploy/ops (`.kamal`, `config/deploy.*`),
     `openapi`, audio, …
   - subsystems — tokenizer/search, SRS/cards, sentence-mining, …
   - a final **Chore** catch-all for shared/cross-cutting files (schema dumps,
     `config/locales`, `config/routes.rb`, the docs tracker, stray UI/docs).
   Aim for a handful of coherent commits, not one-per-file.
3. For every group **except the last**, run:

   ```
   jj split -m "<Feature>: <concise summary>" <path> <path> ...
   ```

   - Passing filesets makes the split non-interactive; `-m` skips the description
     editor. (Never invoke `jj split` without filesets — it opens a diff editor.)
   - The selected paths become a described commit at the current position; the
     remaining changes move into a new child that becomes `@`. So each split peels
     one group off the bottom and you keep operating on `@`.
   - Directory paths (`extension`, `openapi`, `.kamal`, `app/models/anki`) match
     recursively; list individual files otherwise.
4. Whatever is left in `@` is the final group — name it with
   `jj describe -m "<summary>"` (a `Chore: …` commit is fine for the leftovers).
5. Show the result so the user can eyeball it:

   ```
   jj log -r 'trunk()::@' --no-graph -T 'if(current_working_copy, "@ ", "  ") ++ description.first_line() ++ "  [" ++ diff.files().len() ++ " files]\n"'
   ```

## Notes

- jj operations are safe to iterate on: `jj undo` reverses the last one, `jj op log`
  shows history if you need to unwind further.
- If a `jj split` matched no files (typo in a path), fix the path and retry that
  group — the earlier splits are unaffected.
- Report the final stack (commit titles + file counts) to the user; do not paste
  full diffs.
