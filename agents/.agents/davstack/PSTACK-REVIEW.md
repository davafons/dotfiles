# Why davstack selects from pstack

Pstack is an engineering workflow built around Cursor. Davstack keeps selected
workflows, adapts them to David's tools, and leaves project facts in each repo.
A shared file format does not make the runtimes interchangeable.

This review starts from the installed environment, not from an assumption that
upstream must replace it. No skill was imported or updated during this pass.
These are historical review notes, not global agent instructions or an
installation manifest. The local layout and installation contract are in
[the davstack guide](README.md).

## The reference is separate from the installation

On 2026-10-12, upstream `cursor/plugins` main was fetched into
`~/.cache/davstack/upstream/cursor-plugins/` using `jj git clone`.
The fetched revision is
[`e5a02f8fb0409c2db7eb06eae9078b235a2b5009`](https://github.com/cursor/plugins/tree/e5a02f8fb0409c2db7eb06eae9078b235a2b5009/pstack),
with pstack version `0.15.19`. A subsequent GitHub API read reported the same SHA.
The reference checkout had no working-copy changes.

The five direct local imports still record
`d73344bee8cf22e53b9d5f4cf5749d38ba38c174`. The eight migrated personal skills
record their Shirabe origin. Fetching a reference did not change either lineage.

`bin/bin/pstack-inventory <reference-checkout>` produces a read-only JSON
inventory from the actual files. This pass saved its output at
`~/.cache/davstack/upstream/pstack-inventory.json`. The inventory distinguishes
registered skills, playbooks, agent definitions, and dormant automation skills.
Its same-name comparisons report byte differences, not correctness or permission
to overwrite an adaptation.

## The layers do different jobs

The [upstream README](https://github.com/cursor/plugins/blob/e5a02f8fb0409c2db7eb06eae9078b235a2b5009/pstack/README.md)
and the three entry-point skills describe this organization:

```text
User goal and done check
  -> poteto-mode selects a playbook
     -> playbook supplies the ordered steps
        -> workflow skills supply specialized methods
        -> principle skills supply decision rules
        -> agent definitions wrap delegates
        -> scripts support particular playbooks
```

The 52 registered skills divide into 28 workflow skills and 24 `principle-*`
skills. The 23 playbooks are files inside `poteto-mode`, not another 23 slash
commands. `setup-pstack` supplies role configuration. `poteto-help` explains the
routes without starting expensive work for a help question.

The two agent definitions are `poteto-agent` and Comment Sicko. They are not
skills. `poteto-agent` loads the mode for delegates; the parent chat still owns
the playbook. The mode directory also contains scripts for plans, orchestration,
PR watching, and worktree audits. Reading its main `SKILL.md` does not establish
that those scripts are safe or compatible locally.

The guide is documentation, not runtime configuration. The Benny automation pack
has three additional `SKILL.md` files under `automations/`, outside the registered
skill directory. It is dormant and needs a separate setup review.

Pstack also refers to things it does not ship. `deslop`, `control-cli`, and
`control-ui` belong to `cursor-team-kit`. `/loop` and `/create-skill` are Cursor
built-ins. Copying pstack alone would not provide those dependencies here.

## The local split already has a reason

Davstack currently has 13 development skills. Five are selected direct upstream
imports, and eight came through the personal Shirabe workflow. Six personal
workflow facades live beside them. They delegate ordinary personal requests to
provider manuals rather than turning pstack into a mail or calendar system.

`dav-mode` owns routing, 16 local playbooks, and shared working rules. The local
stack does not register the upstream principle catalogue. Several ideas already
live in those shared rules, such as real-artifact proof, preserving shared work,
and preferring structural checks over prose. That does not mean every upstream
principle has been reviewed or deliberately covered.

This distinction matters for authority. Local rules require explicit permission
for delegation, external communication, pushing, and native desktop input where
applicable. Upstream's broader defaults cannot grant that permission.

## Review 1: setup-pstack configures a Cursor runtime

[Source](https://github.com/cursor/plugins/blob/e5a02f8fb0409c2db7eb06eae9078b235a2b5009/pstack/skills/setup-pstack/SKILL.md).
The full main file and guide setup page were read. It has no supporting directory
in this snapshot. Its optional verification-skill dependency remains a separate
review item.

The skill detects models, loads an existing role map, asks for a reasoning budget,
confirms each role, validates slugs, and writes
`~/.cursor/rules/pstack-models.mdc`. Panel list length sets the number of delegates.
It offers a project verification skill when no driving harness exists.

The useful contract is explicit configuration based on detected capabilities.
An unavailable model never silently becomes a claimed configuration. Reruns
preserve deliberate overrides and remove retired roles.

The local mismatch is structural. The exposed child tool accepts an agent name
and brief, not a per-call model or reasoning argument. Yuke's current profile
configures `general` as `openai-codex/gpt-6-luna`. Parent model presets and child
configuration are distinct. A Cursor rule file would not change those settings.
No model entitlement checks or child-model execution were performed.

Recommendation, not an adoption decision: do not install this skill unchanged.
Keep model configuration at the actual harness boundary. Review whether a
portable setup workflow earns its place only after deciding which runtimes and
role controls David wants to support. No budget or model choice was made here.

## Review 2: poteto-mode is a router with substantial dependencies

[Source](https://github.com/cursor/plugins/blob/e5a02f8fb0409c2db7eb06eae9078b235a2b5009/pstack/skills/poteto-mode/SKILL.md).
The full main file, routing guide, and `poteto-agent` definition were read.
The playbook paths and script package manifest were inventoried. Individual
playbooks, principle leaves, and script implementations are not yet reviewed.

The mode matches a task, reads its playbook, and copies the steps into a todo
list before task-specific work. A skipped step stays visible with its reason.
It routes large or unmatched work to `figure-it-out`, and separates one long
run from a standing multi-day program.

Its main file also triggers other workflows. For example, code crossing a
function boundary routes to `architect`; benchmarks route to
`benchmark-checklist`; shipping routes to independent verification. Its
principle index requires reading the leaf rule before citing that rule.

The strongest ideas are explicit task routing, visible skipped steps, and proof
against the real artifact. Davstack already keeps those ideas without importing
the whole catalogue.

The main file cannot replace `dav-mode` unchanged. It assumes Cursor `Task`
fields, background agents, per-role model selection, and custom-mode metadata.
It grants reversible external actions without asking. It also routes every
playbook through PR-opening behavior and relies on uninstalled workflows.
Those assumptions conflict with local authority and runtime boundaries.

Recommendation, not an adoption decision: keep `dav-mode` as the local router.
Review upstream playbooks one at a time for missing methods. A difference in
playbook counts is not evidence that davstack needs seven more playbooks.
An import must have a real trigger, a working local tool path, and proportionate
verification. Nothing in the upstream main file authorizes spawning or shipping
for this review.

## Review 3: poteto-help explains rather than executes

[Source](https://github.com/cursor/plugins/blob/e5a02f8fb0409c2db7eb06eae9078b235a2b5009/pstack/skills/poteto-help/SKILL.md).
The full main file and both references, `prompting.md` and `recipes.md`, were
read. Linked workflows remain separate review items.

The skill distinguishes a help question from a request to do work. For help it
answers, supplies at most one example prompt, and links the source. It explains
close calls such as `how` versus `why`, `arena` versus `swarm`, and `recall` versus
catching up on the current chat.

Its prompting reference favors a goal, a pass-or-fail done check, desired proof,
known facts, and real constraints. That is useful without another installed
skill. The main file explicitly warns that most workflows use Cursor subagents
and may not work in other tools.

Its setup diagnosis does not transfer directly. A missing Cursor role file does
not mean Yuke is unconfigured. Option+Enter, Custom Modes, and `/loop` describe
Cursor, not this harness. The local `plan` skill also means daily planning,
whereas a mode's Plan playbook means multi-session software work.

Recommendation, not an adoption decision: use this as the organization guide.
Avoid a second help router until an actual discovery problem justifies one.
If we add local help later, it must explain installed davstack names and actual
harness behavior rather than point users at unavailable commands.

## The remaining queue is a reading order, not an import list

The first three main skills above have reviews. No remaining entry is approved
by appearing here. The order starts with the capabilities already installed,
then moves into optional design, delegation, and automation workflows.

1. `how`, `why`, `teach`, `recall`.
2. `blast-radius`, `tdd`, `create-verification-skill`, `maintain-verification-skill`.
3. `no-comments`, `unslop`, `technical-writing`, `figure-it-out`, `benchmark-checklist`.
4. `architect`, `arena`, `swarm`, `interrogate`.
5. `show-me-your-work`, `reflect`, `correct`, `automate-me`, `typescript-best-practices`.
6. `ketchup`, `bro`, `make-bot-ui`.

The 24 principles then need individual reads in their upstream groups:

- Core: `laziness-protocol`, `foundational-thinking`,
  `redesign-from-first-principles`, `attack-the-premise`,
  `subtract-before-you-add`, `minimize-reader-load`, `outcome-oriented-execution`,
  `experience-first`, `exhaust-the-design-space`, `build-the-lever`.
- Architecture: `model-the-domain`, `boundary-discipline`,
  `type-system-discipline`, `make-operations-idempotent`,
  `migrate-callers-then-delete-legacy-apis`, `separate-before-serializing-shared-state`.
- Verification: `prove-it-works`, `fix-root-causes`, `sequence-verifiable-units`,
  `test-behavior-not-implementation`, `explain-the-number`.
- Delegation: `guard-the-context-window`, `never-block-on-the-human`.
- Meta: `encode-lessons-in-structure`.

Each principle name above has the `principle-` prefix in its directory name.
The playbooks, scripts, Comment Sicko agent, and dormant automation pack need
separate supporting-file reviews. They must not disappear behind a claim that
all skill main files were read.

For each remaining skill, the review needs its full main file, relevant
references, actual triggers and outputs, local overlap, unavailable dependencies,
authority conflicts, and a keep/adapt/defer/skip recommendation. A recommendation
is not approval to import. Verification must match any behavior we actually change.
