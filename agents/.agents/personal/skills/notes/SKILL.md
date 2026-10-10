---
name: notes
description: "Find, read, create, and update David's Obsidian notes. Use for knowledge and journal notes, not task tracking or calendar scheduling."
---

# Notes

Use the configured Obsidian vault as the source of truth for notes. Resolve its path in this order:

1. The `OBSIDIAN_VAULT` environment variable.
2. `~/Documents/Archivum` when that directory is an existing Obsidian vault.

If neither applies, ask for the vault path; do not search broadly outside the expected location or create a vault.

Use `rg --files` to discover Markdown notes and `rg -n -g '*.md'` to search them. Exclude `.obsidian/`, `.git/`, `.jj/`, and `.stversions/` unless the request is specifically about vault configuration or history.

Before changing a note, find the exact target and read its surrounding context. Preserve its frontmatter, wikilinks, callouts, tags, and local formatting. Note creation, moves, deletion, and substantive edits change synced data: require an explicit request and confirm the target when it is ambiguous. After a write, reread the changed note and report its path.

Never initialize or modify vault version-control metadata. Do not create duplicate tasks in notes: task state belongs to `tasks`, planned time to `calendar`, and day planning to `plan`. Use notes only when David wants durable context, a journal entry, reference material, or a project note.
