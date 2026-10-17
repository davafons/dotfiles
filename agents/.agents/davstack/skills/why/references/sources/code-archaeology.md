# Code Archaeology (jj + in-repo)

Read [the native runtime contract](../../../dav-mode/references/playbook-runtime.md). Vendor tools below are source examples, not assumed services or permission to configure them. Use only available, authorized, read-only evidence tools.

## What this source contains

- Commit history (messages, dates, authors, diffs)
- PR descriptions, review comments, and discussion threads (via `gh`)
- Inline code comments, TODOs, FIXMEs, deprecation notes
- ADRs (architectural decision records) if the repo keeps them
- Tests, whose names and assertions often encode the edge cases that motivated a change
- Related files modified in the same commits (co-change signal)
- CHANGELOG entries and release notes in the repo
- Issue/ticket IDs in commit messages and PR bodies

The most trustworthy source, tied directly to the code, and the most complete. Everything that went through the repo should be here.

## How to search it

Expand the seed commit list:

```bash
# File history; inspect rename diffs and repeat with the old path as needed.
jj log --no-graph --patch --git <file>

# Search these patches for the exact string or regex; jj has no -S or -G flag.
jj log --no-graph --patch --git <file>

# Select the target line range from the annotated output.
jj file annotate <file>

# One revision's full diff.
jj show --git <revision>

# Revisions between two points affecting this file.
jj log --no-graph -r '<old>..<new>' --patch --git <file>
```

Look for out-of-band docs:

```bash
# ADRs often live in docs/adr/ or similar
rg -l -i 'architecture.decision' --glob '*.md'

# TODOs and FIXMEs near the target
rg -n -C2 '(TODO|FIXME|HACK|XXX|NOTE)' <target_file>

# Related tests
rg -l '<symbol>' --glob '*test*'
```
