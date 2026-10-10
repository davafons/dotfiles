# davstack

Davstack selects pstack development workflows and adapts them to David's tools.
Changes beyond runtime and authority adaptations require individual review.
The installed set includes migrated Shirabe workflows whose upstream fidelity
is still under review.

Development sources live in `agents/.agents/davstack/skills/` in dotfiles.
Personal sources live in `agents/.agents/personal/skills/`. Each skill is directly
editable, with its references beside it. No full pstack plugin, archive, generated
skill wrappers, or hidden imports are installed.

The [upstream review](PSTACK-REVIEW.md) records the separate reference snapshot,
organization, and individual skill reviews. It is a reading queue, not an import
list. Both documents are repository-only documentation, not installed skills or
global agent instructions. Current environment facts and the resume state are in
the dotfiles project context and the linked review task in `/work`.

## Skills

| Skill | Purpose | Main dependency |
| --- | --- | --- |
| `dav-mode` | Working mode, task routing, shared working rules | Its 14 playbooks and shared-rules reference |
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

Playbooks are references, not 14 additional registered skills. Their ordered
methods now come from the selected upstream copies, not the abbreviated Shirabe
versions. The [playbook runtime](skills/dav-mode/references/playbook-runtime.md)
records their source revision and the tool, permission, and dependency adaptations.

The restoration keeps plan authoring, characterization-first refactoring,
feature decomposition, live forensic evidence, and exact-patch stack shipping.
Upstream design, judging, coverage, and principle protocols remain linked
references rather than additional installed skills. Missing capabilities keep
the affected gates open; they do not count as successful verification.

## Personal skills outside davstack

`browser`, `calendar`, `mail`, `notes`, `plan`, and `tasks` remain globally
available but are not part of davstack. Their sources have a separate personal
group. Their discovery links share a directory with davstack links; that does
not make them pstack workflows.

The `plan` skill manages David's day and tasks. The
`dav-mode/playbooks/multi-phase-plan.md` reference authors multi-phase or multi-PR
software plans and stops before implementation.
Provider manuals (`hey`, `fizzy`, `wariwari`) and the Yuke-owned `yuke` skill
also remain outside davstack, with their own installation and update ownership.

## Layout

```text
agents/.agents/
├── AGENTS.md
├── davstack/
│   ├── README.md
│   ├── PSTACK-REVIEW.md
│   └── skills/
│       ├── dav-mode/
│       │   ├── SKILL.md
│       │   ├── LICENSE
│       │   ├── references/{working-rules.md,playbook-runtime.md}
│       │   └── playbooks/
│       │       ├── bug-fix.md
│       │       ├── eval.md
│       │       ├── feature.md
│       │       ├── hillclimb.md
│       │       ├── investigation.md
│       │       ├── multi-phase-plan.md
│       │       ├── pause-safely.md
│       │       ├── perf-issue.md
│       │       ├── prototype.md
│       │       ├── refactoring.md
│       │       ├── runtime-forensics.md
│       │       ├── session-pickup.md
│       │       ├── shipping.md
│       │       └── visual-parity.md
│       ├── blast-radius/SKILL.md
│       ├── comment-sicko/{SKILL.md,agents/claude.md,agents/codex.toml}
│       ├── no-comments/SKILL.md
│       ├── reflect/SKILL.md
│       ├── tdd/SKILL.md
│       ├── unslop/{SKILL.md,references/writing.md}
│       ├── figure-it-out/SKILL.md
│       ├── how/{SKILL.md,LICENSE,references/}
│       ├── why/{SKILL.md,LICENSE,references/}
│       ├── teach/{SKILL.md,LICENSE}
│       ├── recall/{SKILL.md,LICENSE}
│       └── create-verification-skill/{SKILL.md,LICENSE,references/feature-map-example/}
└── personal/
    └── skills/
        ├── browser/{SKILL.md,references/}
        ├── calendar/SKILL.md
        ├── mail/SKILL.md
        ├── notes/SKILL.md
        ├── plan/SKILL.md
        └── tasks/SKILL.md
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
Claude Code. It also links the Comment Sicko adapters into
`~/.claude/agents/comment-sicko.md` and `~/.codex/agents/comment-sicko.toml`.
It refuses to replace unmanaged skills or agents. Providers remain outside
dotfiles and keep their existing ownership.
The installer also links the six personal skills into `~/.agents/skills/`.

The source groups are independent of the flat runtime discovery directories.
Stow excludes both source groups; `agent-skills link` owns the per-skill links.
It repoints links to the previous dotfiles source paths during the layout
migration, but still refuses unrelated links or user-owned files.

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
To use the specialist in Claude or Codex, explicitly request delegation to
`comment-sicko` with the files or diff to review. Its caller verifies the report
and applies accepted changes. Both adapters read the canonical skill rather
than duplicate its review rules.

Installation tests do not prove interactive discovery or model behavior in
Claude or Codex.

## Shirabe migration

The original migration brought eight definitions from `docs/agents/`, 16
playbooks, the Comment Sicko agent, and the portable writing standard here.
The current set keeps 14 playbooks after removing the local-only `encode` and
`write` routes. The initial naming cleanup gave seven playbooks their upstream
counterpart filenames without changing methods. A subsequent restoration replaced
all 14 methods with upstream copies and adapted their runtime references.
The mode's original metadata still records its Shirabe lineage; the playbook
runtime records the separate upstream source and license.

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
  `technical-writing/SKILL.md`, not a duplicate project document.
- Repository instructions supply commands, architecture, and checkpoint format;
  Rails, `bin/brief`, ratchets, and Shirabe paths are not global prerequisites.
- Delegation requires an explicit user request. Otherwise review lenses run
  serially, with no claim of independence. Agent eval reports missing independent
  runs instead of simulating them.
- Both Comment Sicko adapters inherit the configured model. Claude permits only
  Read/Grep/Glob; its caller does shell/history checks. The Codex TOML adapter
  requests a read-only sandbox and leaves executable checks to its caller.
  Codex reapplies the parent's live permission overrides, so the adapter does
  not guarantee isolation from a parent running with broader permissions.
  Other harnesses use the same report-only skill without enforced tool isolation.
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
`maintain-verification-skill` remain uninstalled. The session-pickup *playbook*
is an adapted upstream playbook, not an installation of that separate skill.

`create-verification-skill` writes `.agents/skills/verify-<app>/` for Yuke/Codex
or `.claude/skills/verify-<app>/` for Claude, in the project, not dotfiles. Improve
an existing verification skill in place. Its Notes feature maps are format
examples, not proof. A safe live run of one mapped feature, with evidence that
survives cleanup, is required before calling the generated skill verified.

Skill-related tests cover isolated/idempotent installation, global link targets,
and refusal to overwrite unmanaged skills or agents. They live in `Makefile`
and `bin/tests/test_{investigation_skills,davstack_migration}.py`. They do not
assert skill prose, reference structure, or metadata. The check target does not
run the Codex skill-format validator. New upstream skills still require individual
review and approval.
