# davstack

Davstack selects pstack development workflows and adapts them to David's tools.
Changes beyond runtime and authority adaptations require individual review.
The installed set includes migrated Shirabe workflows. The
[upstream follow-up](UPSTREAM-FOLLOWUP.md) records restored `how` and `reflect`
methods, native discovery evidence, and the remaining model-dependent gates.

Development sources live in `agents/.agents/davstack/skills/` in dotfiles.
Personal sources live in `agents/.agents/personal/skills/`. Each skill is directly
editable, with its references beside it. No full pstack plugin, archive, generated
skill wrappers, or hidden imports are installed.

The [upstream review](PSTACK-REVIEW.md) records the separate reference snapshot,
organization, and individual skill reviews. It is a reading queue, not an import
list. Both documents are repository-only documentation, not installed skills or
global agent instructions. Current environment facts and the resume state are in
the linked task notes in `/work`.

## Current source set

Davstack contains **59 global development skills**, **23 playbooks**, and
**three project verification skills**. The global set includes all **30 workflow
skills** and all **24 principle skills** registered by pstack 0.15.25, with
`poteto-mode` adapted as `dav-mode`. Principles are local skills, not remote-only
references, and are linked from the mode's index.

The complete pstack methods and supporting references use
[`101b274dd991f694e1f7024be2157e5f3adf07de`](https://github.com/cursor/plugins/tree/101b274dd991f694e1f7024be2157e5f3adf07de/pstack),
confirmed as upstream main on October 17, 2026. The sync restores full upstream
bodies where older Shirabe migrations had rewritten or shortened them. It also
updates Ketchup, the principle definitions, model-effort guidance, lead judgment,
autopilot and shipping policies, and the watcher's owner-approval classification.
Every imported pstack skill carries the exact upstream MIT notice.

The five additional skills have separate sources:

- Comment Sicko exposes the complete pstack agent method at the same pin through
  a report-only native skill and agents.
- Control CLI and Deslop come from `cursor-team-kit` at that pin. Their source
  bodies have not changed since the prior pin; native adapters and exact Cursor
  MIT notices remain.
- Loop maps the upstream built-in to the actual native scheduler.
- The complete public Anthropic Skill Creator stays at its independent approved
  pin `dbd4588f9e1033efb41dad4bef2f7947c8993d44`, under Apache-2.0. This pstack sync
  does not claim it is Cursor's built-in or refresh an unrelated upstream.

Runtime differences remain explicit in
[Playbook runtime](skills/dav-mode/references/playbook-runtime.md). Cursor tools,
model tables, configuration recipes and bot APIs retained in source bodies are
upstream examples, not native capabilities. Actual native roles, lifecycle,
permissions and jj commands govern execution. Missing independent seats,
cloud placements, or bot/secret APIs leave their execution gates open.

The program store deliberately retains jj ancestry, explicit program scope and
forge-head checks rather than adopting upstream's Git/base-chain resolver. It
currently supports GitHub, not the new Origin frontier selector. Workspace cleanup
uses the read-only jj auditor instead of the upstream Git/transcript scanner.
These are runtime adapters, not claims of complete helper-platform parity.

Two local additions are not upstream method changes. The user explicitly approved
"execute the smallest useful case first" in shared working rules. The TypeScript
adapter records a demonstrated source erratum: a plain-number duration does not
prove nonnegativity, finiteness or Date-range validity. The source example remains
intact. Other engineering summaries in shared rules now defer to the local
upstream principle leaves instead of overriding them.

The dormant Benny automation pack and generated Claude plugin tree are not
installed. Their complete source remains in the separate upstream checkout.
This is complete registered-method coverage, not byte-for-byte plugin packaging.

Source, license, link, installation and helper checks are distinct from model
workflow efficacy. The earlier model campaign remains stopped. No source copy
resumes it, configures providers, scans personal history, installs bot services,
reloads active sessions, publishes, or merges. Save drafts and finish active turns
before refreshing a frontend.

## Start reading and using the stack

Start with [dav-mode](skills/dav-mode/SKILL.md), then read the playbook matching
your task under `skills/dav-mode/playbooks/`. A skill's `SKILL.md` gives its trigger,
method and output. Read its supporting references when the method names them.
The files here are the canonical sources linked into `~/.agents/skills/`.

You can request skills in ordinary language. For example, ask how a subsystem
works, ask for a regression before a bug fix, ask Architect to design an API,
or ask Interrogate to challenge a change. Delegated workflows still need explicit
delegation permission. Read-only review does not authorize applying its findings.

All registered upstream workflows and principles now have local sources at the
same pin. Cursor-only capabilities still require actual native equivalents;
reading and copying the method do not execute it.

## Skills

| Skill | Purpose | Main dependency |
| --- | --- | --- |
| `dav-mode` | Working mode, task routing, shared working rules | Its 23 playbooks, runtime adapters, and native helpers |
| `blast-radius` | Find what a change breaks beyond the diff; prove its safety facts | Real code and the project's checks |
| `comment-sicko` | Report-only comment review, precise cuts, confusing code, missing guards | In-scope source files |
| `no-comments` | Verify the review, apply accepted cuts, fix unclear code | `comment-sicko` and the project's checks |
| `reflect` | Judgment, tooling, and divergent review; Accepted / Rejected / Backlog synthesis | Session evidence, reviewer templates, and approval before skill edits |
| `tdd` | Watch a focused regression fail before fixing it, then pass | A practical executable test or repro |
| `benchmark-checklist` | Vet performance measurements against seven evidence questions | Real measurements and supported platform diagnostics |
| `show-me-your-work` | Keep an append-only decision trail and audit it before handoff | Its logger, current-session evidence, and independent review when authorized |
| `unslop` | Cut AI tells from writing | Its pattern catalog |
| `technical-writing` | Apply Diátaxis, sentence, instruction, and syntax rules | `unslop` |
| `deslop` | Remove AI code patterns from the scoped diff | Project conventions and checks |
| `loop` | Schedule authorized recurring agent turns | An available native scheduler |
| `figure-it-out` | Design and execute an auditable workflow for large or unmatched work | A falsifiable goal and the project's checkpoint format |
| `how` | Explain entry points, flow, boundaries, file map, and gotchas | Its explorer/explainer references |
| `why` | Investigate historical reasons, confidence, contradictions, and gaps | Available history, PRs, and read-only evidence tools |
| `teach` | Build a plain explanation at the reader's pace | `how`, `why`, and `unslop` |
| `recall` | Reconstruct current state, threads, problems, and next move | Authorised in-scope history and `why` |
| `create-verification-skill` | Generate a project-local driving and verification skill with retained proof | A runnable app and safe control harness |
| `maintain-verification-skill` | Audit every mapped feature from source and live behavior | Project verification skill, authorized source readers, and coordinator-owned driving |
| `control-cli` | Drive, inspect, and profile an interactive terminal app | Existing project harness or isolated PTY/private tmux |
| `skill-creator` | Full authoring, paired evals, human review, iteration, and description optimization | Authorized bounded native model runs, feedback, and its full helpers/templates |
| `swarm` | Parallel coverage, races, and consolidated evidence with explicit gaps | Authorized native workers and owned outputs |
| `arena` | Independent candidates, cross-judging, base selection, and synthesis | Configured candidate/judge seats and verified output isolation |
| `architect` | Usage-first designs, distinct sketches, and implementation against synthesis | `how`, `why`, `arena`, and its three design templates |
| `interrogate` | Distinct-model adversarial review with lead judgment and no automatic edits | Fresh review-only sessions, complete reviewer templates, and engine model receipts |
| `correct` | Make demonstrated repeat mistakes structurally impossible within the requested scope | Real repeated evidence, architecture or executable checks, and past-mistake reproduction |
| `ketchup` | Recap this chat since the user's last message and explain user-only decisions | Read-only current-chat evidence and `bro` |
| `bro` | Restate the last assistant reply in plain language | The previous reply |
| `automate-me` | Capture working conventions in a personal mode | Authorized history, `skill-creator`, `unslop` and user feedback |
| `typescript-best-practices` | Apply the complete TypeScript rules and examples | Referenced principles and the documented duration erratum |
| `setup-pstack` | Detect, confirm and configure model roles and budgets | Actual native role configuration, not a decorative Cursor rule |
| `poteto-help` | Explain the skill map and hand back a suitable prompt without starting work | Complete router, prompting/recipe references and native mappings |
| `make-bot-ui` | Build a UI that wakes a bot through a server-side webhook | Supported bot/secret APIs and separately authorized infrastructure |
| `in-your-own-words` | Restate the user's goals and underlying problem | The current request |
| `sharpen` | Frame a task around expert methods and the actual goal | Current context and an appropriate outside check |

The 23 playbooks are references, not additional registered skills. Their ordered
methods now come from the selected upstream copies, not the abbreviated Shirabe
versions. The [playbook runtime](skills/dav-mode/references/playbook-runtime.md)
records their source revision and the tool, permission, and dependency adaptations.

The restoration keeps plan authoring, characterization-first refactoring,
feature decomposition, live forensic evidence, and exact-patch stack shipping.
Design, judging, and coverage methods now use the installed `swarm`, `arena`,
`architect`, and `interrogate` skills. Principle leaves remain linked upstream
references, not additional registered skills. Missing capabilities keep the
affected gates open; they do not count as successful verification.

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
│       │   ├── agents/{claude.md,codex.toml,yuke.js}
│       │   ├── scripts/{check-plan.mjs,patch-id.mjs,workspace-audit.py,orch/,watch-pr/}
│       │   ├── references/{working-rules.md,playbook-runtime.md}
│       │   └── playbooks/
│       │       ├── authoring-a-skill.md
│       │       ├── autonomous-run.md
│       │       ├── autopilot-full.md
│       │       ├── autopilot-stack.md
│       │       ├── babysit.md
│       │       ├── bug-fix.md
│       │       ├── eval.md
│       │       ├── feature.md
│       │       ├── hillclimb.md
│       │       ├── investigation.md
│       │       ├── multi-phase-plan.md
│       │       ├── opening-a-pr.md
│       │       ├── orchestrate.md
│       │       ├── pause-safely.md
│       │       ├── perf-issue.md
│       │       ├── prototype.md
│       │       ├── refactoring.md
│       │       ├── runtime-forensics.md
│       │       ├── session-pickup.md
│       │       ├── shipping.md
│       │       ├── trace-forensics.md
│       │       ├── visual-parity.md
│       │       └── worktree-cleanup.md
│       ├── blast-radius/SKILL.md
│       ├── comment-sicko/{SKILL.md,agents/claude.md,agents/codex.toml}
│       ├── no-comments/SKILL.md
│       ├── reflect/{SKILL.md,LICENSE,references/}
│       ├── tdd/SKILL.md
│       ├── unslop/{SKILL.md,LICENSE}
│       ├── technical-writing/{SKILL.md,LICENSE}
│       ├── deslop/{SKILL.md,LICENSE}
│       ├── loop/SKILL.md
│       ├── benchmark-checklist/{SKILL.md,LICENSE}
│       ├── show-me-your-work/{SKILL.md,LICENSE,references/,scripts/log.sh}
│       ├── figure-it-out/SKILL.md
│       ├── how/{SKILL.md,LICENSE,references/}
│       ├── why/{SKILL.md,LICENSE,references/}
│       ├── teach/{SKILL.md,LICENSE}
│       ├── recall/{SKILL.md,LICENSE}
│       ├── skill-creator/{SKILL.md,LICENSE.txt,NOTICE.md,agents/,assets/,eval-viewer/,references/,scripts/}
│       ├── swarm/{SKILL.md,LICENSE}
│       ├── arena/{SKILL.md,LICENSE}
│       ├── architect/{SKILL.md,LICENSE,references/}
│       ├── interrogate/{SKILL.md,LICENSE,references/}
│       ├── correct/{SKILL.md,LICENSE}
│       ├── ketchup/{SKILL.md,LICENSE}
│       ├── bro/{SKILL.md,LICENSE}
│       ├── automate-me/{SKILL.md,LICENSE}
│       ├── typescript-best-practices/{SKILL.md,LICENSE,references/}
│       ├── setup-pstack/{SKILL.md,LICENSE}
│       ├── poteto-help/{SKILL.md,LICENSE,references/}
│       ├── make-bot-ui/{SKILL.md,LICENSE}
│       ├── in-your-own-words/{SKILL.md,LICENSE}
│       ├── sharpen/{SKILL.md,LICENSE}
│       ├── control-cli/{SKILL.md,LICENSE}
│       ├── maintain-verification-skill/{SKILL.md,LICENSE}
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

The installer explicitly lists all 59 davstack names. It links their complete
directories into `~/.agents/skills/` for Yuke/Codex and `~/.claude/skills/` for
Claude Code. It also links the `comment-sicko` and `dav-agent` adapters into
`~/.claude/agents/` and `~/.codex/agents/`. The adapters inherit configured models.
The Yuke profile registers its own `dav-agent` adapter from the canonical source.
It refuses to replace unmanaged skills or agents. Providers remain outside
dotfiles and keep their existing ownership.
The installer also links the six personal skills into `~/.agents/skills/`.

The source groups are independent of the flat runtime discovery directories.
Stow excludes both source groups; `agent-skills link` owns the per-skill links.
It repoints links to the previous dotfiles source paths during the layout
migration, but still refuses unrelated links or user-owned files.

`dav-mode` is opt-in. Invoke it explicitly with `$dav-mode` or the frontend's
skill picker. Global instructions do not automatically activate it for multi-step
work. Other skills remain usable individually without enabling the mode.

The shared global instructions apply across projects in frontends that load them.
Yuke uses `~/.agents/AGENTS.md`. The Codex entrypoint and Claude source template
link to the same canonical file. These defaults supplement repository instructions;
they do not replace the local `AGENTS.md` or the frontend's project instructions.

Existing chats can retain old instruction snapshots. In Yuke, save any draft and
use `/reload` when idle, or start a new chat. Explicit invocation examples:

```text
/skill:dav-mode
/skill:blast-radius review this change
/skill:no-comments this file
/skill:reflect
/skill:tdd
/skill:unslop this draft
/skill:technical-writing this document
/skill:deslop
/skill:benchmark-checklist
/skill:show-me-your-work
/skill:loop
/skill:figure-it-out
/skill:how does the importer work?
/skill:why did we choose this format?
/skill:teach explain the boundary
/skill:recall my importer work
/skill:control-cli
/skill:skill-creator
/skill:maintain-verification-skill
/skill:create-verification-skill
/skill:swarm
/skill:arena
/skill:architect
/skill:interrogate
```

Claude uses the matching global skill names; Codex can select/request the skills
by name. Skill links do not install Yuke plugins. The separate profile's `session-loop`
plugin supplies `/loop` and the `loop` model tool.
To use the specialist in Claude or Codex, explicitly request delegation to
`comment-sicko` with the files or diff to review. Its caller verifies the report
and applies accepted changes. Both adapters read the canonical skill rather
than duplicate its review rules.

Installation tests do not prove interactive discovery or model behavior.
The optional `python3 -B bin/tests/check_agent_discovery.py` driver checks actual
Claude directory discovery and offline Codex startup. It leaves Codex catalog
discovery and active-agent execution explicitly unverified.

## Runtime boundaries and helpers

The [playbook runtime](skills/dav-mode/references/playbook-runtime.md#native-helpers)
lists the plan validator, stable patch fingerprint, GitHub PR watcher, and program
store commands. The store reads jj topology, not PR base refs, for its frontier.
It does not start agents or schedule turns.

`benchmark-checklist` retains upstream's seven measurement questions and uses
supported macOS diagnostics. `show-me-your-work` retains the upstream TSV format,
logger, transcript audit, and independent-review gate. Its default state directory
stays outside jj snapshots. `trace-forensics` diagnoses an existing capture, while
`runtime-forensics` captures and probes a live process. Neither requires a cloud
worker. This Mac can run CLI, API, isolated terminal, browser, and authorized
computer-use verification. Native desktop activation and system-wide input still
need permission for the run. A model-free run excludes additional model calls,
not local computer access.

The [loop skill](skills/loop/SKILL.md) describes the scheduler contract. Yuke's
profile supplies a session-bound timer. Quit or profile reload stops it.
Restart requires explicit rearming. There is no daemon or saved schedule, and
installation starts no recurring work. Claude and Codex have no scheduler adapter
in this installation. An unavailable native scheduler leaves that gate open.

The source inventory is reproducible from the dotfiles root:

```sh
find agents/.agents/davstack/skills -mindepth 1 -maxdepth 1 -type d | sort
find agents/.agents/davstack/skills/dav-mode/playbooks -name '*.md' | sort
```

## Shirabe migration

The original migration brought eight definitions from `docs/agents/`, 16
playbooks, the Comment Sicko agent, and the portable writing standard here.
The initial cleanup kept 14 playbooks after removing the local-only `encode`
and `write` routes. The initial naming cleanup gave seven playbooks their upstream
counterpart filenames without changing methods. A subsequent restoration replaced
all 14 methods with upstream copies and adapted their runtime references.
The approved expansion added Autonomous run, Autopilot-full, Autopilot-stack,
Orchestrate, Babysit, and Opening a PR from the same pinned source. The current
set has 23 playbooks after Trace forensics, skill authoring, and workspace cleanup, with the
full upstream mode principles and methods retained.
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
- Comment constraints follow the complete upstream keep-list and No Comments
  procedure, including its explicit encoding approvals. Reflection still waits
  for approval before applying proposed edits.
- jj and shared-desktop restrictions apply throughout. Production access and
  deployment require applicable authority, regardless of a playbook's wording.

## Upstream workflow sources

All registered pstack workflows and principles now use the source pin in
**Current source set** above. Earlier import pins and campaign results in the
repository-only reports are historical evidence, not the current inventory.
Runtime adapters cover actual tools/models, authority, jj, privacy and desktop
safety without substituting shorter methods.

`teach` uses Mermaid/ASCII when image generation is absent. `recall` uses only
authorized current-harness history, not unrelated chats or invented session IDs.
`automate-me` is installed; use it only for a requested personal-mode workflow.
Session pickup is the installed `dav-mode` playbook, not a separate global skill.

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

## Verification and control batch

`control-cli` and `maintain-verification-skill` retain their complete methods
from `101b274dd991f694e1f7024be2157e5f3adf07de`, with MIT licenses. Control CLI
comes from `cursor-team-kit`; maintenance comes from pstack. Runtime changes
use private terminal sessions, retained proof, native delegation, jj, and
explicit desktop/publication authority. The maintenance method still requires
its independent source wave and every-feature live pass for a complete result.

This repository owns three local skills, not additional global imports:

- [verify-yuke-profile](../../../.agents/skills/verify-yuke-profile/SKILL.md)
  covers composer/reload, model controls, build status, and native child routing.
- [verify-herdr-profile](../../../.agents/skills/verify-herdr-profile/SKILL.md)
  covers Code ordering, indexed shortcuts, and Yuke notifications.
- [verify-neovim-profile](../../../.agents/skills/verify-neovim-profile/SKILL.md)
  covers project pickers/completion, diff review, and Markdown rendering.

Each has a feature map and reuses the existing driver. Their sources are under
`.agents/skills/`; `.claude/skills/` links the same sources. Native Yuke catalog
discovery was exercised in an isolated profile. All ten mapped features were
driven, with passing evidence retained outside the checkout. An additional
Code-order repeat failed its initial multi-editor order and a fresh-instance
retry passed; stability remains open. This is generation and behavior proof,
not a completed delegated maintenance wave or real model review.
The [batch report](VERIFICATION-BATCH.md) records evidence and limits.

The imported [authoring playbook](skills/dav-mode/playbooks/authoring-a-skill.md)
now uses the installed [skill-creator](skills/skill-creator/SKILL.md). The user
approved the complete public Anthropic method at `dbd4588f9e1033efb41dad4bef2f7947c8993d44`,
with Apache-2.0 license and all supporting files. It is not Cursor's unpublished
built-in. Native helpers were exercised with bounded real Codex tasks and
selection/proposal trials; full campaigns and human feedback are not implied.
See [the authoring port report](AUTHORING-PORT.md). The imported
[cleanup playbook](skills/dav-mode/playbooks/worktree-cleanup.md) uses a native
read-only jj audit. It never infers safe deletion from an empty snapshot or old
commit. PR/chat usage, unsaved buffers, and untracked/ignored data need separate
evidence and explicit approval before cleanup.

The Yuke profile adds `reviewer` on `openai-codex/gpt-6.1-sol` at `xhigh`, leaving
`general` and `dav-agent` defaults unchanged. Spawn results retain engine-accepted
model/effort receipts; child request hooks log selected models. The native guard
checks actual child settings, stored histories, localhost request payloads, depth
limits, and project skill discovery. Scripted provider replies prove plumbing,
not LLM judgment, authentication, a read-only sandbox, or model-family diversity.
Codex-only review cannot close different-family gates. Claude/Codex standalone
agent adapters keep their existing model inheritance; this reviewer role is Yuke-specific.

## Design and coordination batch

The initial October 17 imports added `swarm`, `arena`, `architect`, and
`interrogate` at `1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def`. All 11 upstream main
and reference files are retained, with the pstack MIT license in each directory.
The initial import adapted only source attribution, runtime, workspace, and
authority passages. A later formatting-only cleanup added missing blank lines and
fence languages and repaired heading levels without changing method wording.
The [native coordination contract](skills/dav-mode/references/playbook-runtime.md#design-and-coordination)
owns shared model, lifecycle, output-root, and review restrictions.

Architect retains arena as a dependency and requires two distinct usage-first
designs before synthesis. Arena retains its held-back rubric, fresh cross-judge,
base selection, grafts, and verification. Interrogate keeps the complete reviewer
prompt, rubric, code-quality lens, and lead judgment framework. It returns
findings, not automatic edits. Swarm keeps upfront coverage or race rules,
exact-revision receipts, and explicit gaps when workers fail or drop out.

Distinct-model review is not different-family review. Existing configured Luna
and Sol roles can support the former. Arena prefers a different-family judge;
Eval requires one. Existing Grok availability was observed later, but no completed
auditable different-family verdict was produced; the earlier campaign is stopped.
Yuke's spawn tool keeps the parent workspace root and does not enforce read-only
access. An output directory in a brief is not proof of tool-root isolation.

Installer checks and cold native catalog discovery validate registration only.
No model-backed candidate, reviewer, multiworker dispatch, isolation, or blinding
trial is implied by these imports. Those checks need separate authorization and
retained actual artifacts. No provider, child-tool API, or active session is
changed to install these skills. Save drafts and refresh skills only after active
turns finish. The earlier eight-session authoring grant remains exhausted.
