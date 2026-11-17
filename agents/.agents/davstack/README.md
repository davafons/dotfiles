# davstack

David's editable copy of [pstack](https://github.com/cursor/plugins/tree/main/pstack),
taken from its generated Claude Code tree (`harness/pstack/claude-code`), plus
`control-cli` and `deslop` from `cursor-team-kit`. `UPSTREAM` holds the commit it
was last merged from.

`bin/bin/agent-skills link` links every folder in `skills/` into `~/.claude/skills`
and `~/.agents/skills`, and the two `agents/` into `~/.claude/agents`, so an edit
here applies at once. Skills keep pstack's Cursor wording; each one starts by
reading [the Claude Code adapter](docs/harness/claude-code.md), which maps
Cursor names to Claude Code and git steps to jj.

## Edit

Change any file directly and commit it. Put Claude Code or jj rules that apply
across skills in the adapter rather than in each skill, so upstream updates
merge with fewer conflicts.

## Update

```bash
bin/bin/davstack-sync --status   # pinned commit and upstream main
bin/bin/davstack-sync            # merge upstream main into local edits
```

The sync renames `poteto-mode` to `dav-mode` and `poteto-agent` to `dav-agent`,
drops the `pstack:` prefixes, points adapter links at this folder, and strips the
Cursor model slug from agents. It then merges upstream's change since the pin
into these files with `diff3`. A file both sides changed on the same lines keeps
conflict markers, and the command lists it. Resolve those, review
`jj diff --git`, run `agent-skills link` for new skills, and commit.

Upstream files are MIT, Lauren Tan; see `LICENSE`.
