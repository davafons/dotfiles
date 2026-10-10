# davstack

David's personal, project-independent working stack. The source of truth is
`agents/.agents/skills/` in dotfiles. Each skill is directly editable, with its
references beside it. No full pstack plugin, archive, generated skill wrappers,
or hidden imports are installed.

## Skills

| Skill | Purpose | Main dependency |
| --- | --- | --- |
| `dav-mode` | Working mode, task routing, shared working rules | Its 16 playbooks and shared-rules reference |
| `blast-radius` | Find what a change breaks beyond the diff; prove its safety facts | Real code and the project's checks |
| `comment-sicko` | Report-only comment review, precise cuts, confusing code, missing guards | In-scope source files |
| `no-comments` | Verify the review, apply accepted cuts, fix unclear code | `comment-sicko` and the project's checks |
| `reflect` | Mine durable lessons and propose the strongest encoding | Session evidence; approval before applying |
| `tdd` | Watch a focused regression fail before fixing it, then pass | A practical executable test or repro |
| `unslop` | Cut AI tells; write in one Diátaxis mode | Its writing reference |
| `figure-it-out` | Design and execute an auditable workflow for large or unmatched work | A falsifiable goal and the project's checkpoint format |
| `how` | Explain entry points, flow, boundaries, file map, and gotchas | Its explorer/explainer references |
| `why` | Investigate historical reasons, confidence, contradictions, and gaps | Available history, PRs, and read-only evidence tools |
| `teach` | Build a plain explanation at the reader's pace | `how`, `why`, and `unslop` |
| `recall` | Reconstruct current state, threads, problems, and next move | Authorised in-scope history and `why` |
| `create-verification-skill` | Generate a project-local driving and verification skill with retained proof | A runnable app and safe control harness |

The existing `browser`, `calendar`, `mail`, `notes`, `plan`, and `tasks` skills
remain alongside davstack. The `plan` skill manages David's day and tasks; the
`dav-mode/playbooks/plan.md` reference handles software work spanning sessions.
Playbooks are references, not 16 additional registered skills.

## Layout

```text
agents/.agents/
├── AGENTS.md
├── DAVSTACK.md
└── skills/
    ├── dav-mode/
    │   ├── SKILL.md
    │   ├── references/working-rules.md
    │   └── playbooks/
    │       ├── agent-eval.md
    │       ├── bug-fix.md
    │       ├── encode.md
    │       ├── feature.md
    │       ├── forensics.md
    │       ├── hillclimb.md
    │       ├── investigate.md
    │       ├── pause-safely.md
    │       ├── perf.md
    │       ├── plan.md
    │       ├── prototype.md
    │       ├── refactor.md
    │       ├── session-pickup.md
    │       ├── ship.md
    │       ├── visual-parity.md
    │       └── write.md
    ├── blast-radius/SKILL.md
    ├── comment-sicko/{SKILL.md,agents/claude.md}
    ├── no-comments/SKILL.md
    ├── reflect/SKILL.md
    ├── tdd/SKILL.md
    ├── unslop/{SKILL.md,references/writing.md}
    ├── figure-it-out/SKILL.md
    ├── how/{SKILL.md,LICENSE,references/}
    ├── why/{SKILL.md,LICENSE,references/}
    ├── teach/{SKILL.md,LICENSE}
    ├── recall/{SKILL.md,LICENSE}
    └── create-verification-skill/{SKILL.md,LICENSE,references/feature-map-example/}
```

`why/references/sources/` contains seven evidence-category examples and an
incident/postmortem lens. Linear, Notion, Slack, Datadog, Sentry, and Databricks
are examples, not installed services or registered skills. Missing tools are
gaps, not permission to invent evidence or infer author intent from code.

## Install and use

From the dotfiles root:

```sh
bin/bin/agent-skills link
bin/bin/agent-skills check
make check
```

The installer explicitly lists all 13 davstack names. It links their complete
directories into `~/.agents/skills/` for Yuke/Codex and `~/.claude/skills/` for
Claude Code. It also links the Comment Sicko agent definition into
`~/.claude/agents/comment-sicko.md`. It refuses to replace unmanaged skills or
agents. Providers remain outside dotfiles and keep their existing ownership.

Global `AGENTS.md` starts multi-step development work with `dav-mode` unless
the user opts out. The skill is also directly invokable. In Yuke, use `/reload`
or start a new chat after installation, then:

```text
/skill:dav-mode
/skill:blast-radius review this change
/skill:no-comments this file
/skill:reflect
/skill:tdd
/skill:unslop this draft
/skill:figure-it-out
/skill:how does the importer work?
/skill:why did we choose this format?
/skill:teach explain the boundary
/skill:recall my importer work
/skill:create-verification-skill
```

Claude uses the matching global skill names; Codex can select/request the skills
by name. This does not add custom Yuke slash aliases or change its profile.
Static validation and installation tests do not prove interactive discovery in
Claude or Codex.

## Shirabe migration

All eight definitions from `docs/agents/`, the 16 playbooks, the Comment Sicko
agent, and the portable writing standard now live here. The definitions record
their original path and Shirabe revision in metadata. Names and workflow/output
contracts remain intact where compatible with the runtime.

Shirabe no longer has those source files, generated `.agents/skills/` or
`.claude/skills/` wrappers, its local Comment Sicko wrapper, or `bin/skills`.
Its `AGENTS.md` points at the global stack. Project-specific integrations stay
in `docs/conventions/agent-workflows.md`: Rails commands, SQLite/cache traps,
ratchets, observability, plan schema, locales, and deployment boundaries. Those
are project facts, not a second copy of the portable workflows. Project CI does
not require David's home-directory skills.

Portability changes are explicit:

- Shared rules have one owner in `dav-mode/references/working-rules.md`; comment
  review rules have one owner in `comment-sicko`. The writing standard is in
  `unslop/references/writing.md`, not a duplicate project document.
- Repository instructions supply commands, architecture, and checkpoint format;
  Rails, `bin/brief`, ratchets, and Shirabe paths are not global prerequisites.
- Delegation requires an explicit user request. Otherwise review lenses run
  serially, with no claim of independence. Agent eval reports missing independent
  runs instead of simulating them.
- Claude's Comment Sicko agent has only Read/Grep/Glob and inherits the configured
  model. Its caller does shell/history checks. Other harnesses use the same
  report-only skill without claiming enforced tool isolation.
- A load-bearing comment constraint is retained until encoded or disproved;
  blind deletion must not lose a contract. Encodings and reflection still wait
  for approval where their workflows require it.
- jj and shared-desktop restrictions apply throughout. Production access and
  deployment require applicable authority, regardless of a playbook's wording.

## Selected upstream skills

The five investigation/verification skills were selected from
[cursor/plugins pstack](https://github.com/cursor/plugins/tree/d73344bee8cf22e53b9d5f4cf5749d38ba38c174/pstack)
at `d73344bee8cf22e53b9d5f4cf5749d38ba38c174`, with their MIT licenses and
upstream attribution. Their references retain upstream wording. Each skill has
an explicit Runtime adaptation covering actual tools/models, user authority,
read-only evidence, jj, privacy, and desktop safety.

`teach` uses Mermaid/ASCII when image generation is absent. `recall` uses only
authorised current-harness history, not unrelated chats or invented session IDs.
Optional upstream `session-pickup`, `automate-me`, and
`maintain-verification-skill` remain uninstalled; the session-pickup *playbook*
above is the pre-existing personal workflow, not that upstream skill.

`create-verification-skill` writes `.agents/skills/verify-<app>/` for Yuke/Codex
or `.claude/skills/verify-<app>/` for Claude, in the project, not dotfiles. Improve
an existing verification skill in place. Its Notes feature maps are format
examples, not proof. A safe live run of one mapped feature, with evidence that
survives cleanup, is required before calling the generated skill verified.

Checks cover all personal skill directories, local links, every playbook's
routing, metadata, isolated/idempotent installation, and refusal to overwrite
unmanaged skills or agents. They live in the existing `Makefile` and
`bin/tests/test_{investigation_skills,davstack_migration}.py`. New upstream
skills should still be reviewed and approved individually.
