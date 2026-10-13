---
name: dav-mode
description: The working mode. Names the playbook it matched, commits to its steps before starting, and carries the rules that hold whatever the task is. Read it at the start of any multi-step task.
metadata:
  origin: shirabe
  origin-path: docs/agents/dav-mode.md
  origin-revision: 968e24d69837e3efecca31487f7d8e8508e803c8
---

# dav-mode

Read [Playbook runtime](references/playbook-runtime.md) and the [shared working rules](references/working-rules.md).
These adapt tools and authority, not the upstream task methods. Project-specific facts belong in `AGENTS.md`.

## Non-negotiables

The Principles section below grounds every trigger. Its pinned leaf protocols are source references, not additional installed skills. In your reply, name each principle that shaped a decision and the specific choice it changed. Cite only principles whose leaf SKILL.md you read this session.

Remaining triggers:

- Nontrivial change, architecture decision, or "are we sure?" → the **how** skill.
- About to use the current clarification tool on a "which approach", "how should I", or "what should this do" fork → classify it before you ask. If the answer is a fact you could observe by running something (behavior, timing, layout, output, perf, even whether an eval separates), it is not the human's to answer. Sketch it via the Prototype playbook (`playbooks/prototype.md`) and let the result decide. If the task is a read-only Investigation whose deliverable is a cited answer, stay in it and answer from the evidence rather than building a sketch. Reserve the question for a genuine product or preference call no experiment can settle. Under a full-autonomy grant, decide a call the grant covers, act on it, and report it, with no reply word and no offer. For a decision the operator must make, use the current harness's clarification mechanism and pause dependent work. A pending question is not an answer or approval. Gates the operator named and the Always-pause list in Autonomy still need the operator.
- Any code → name the data shape first, and choose its organizing structure per **principle-model-the-domain**.
- Code crossing a function boundary → the [architect protocol](https://github.com/cursor/plugins/blob/1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def/pstack/skills/architect/SKILL.md), independent design exploration before implementing when delegation is authorized.
- Parallel fan-out → the [swarm protocol](https://github.com/cursor/plugins/blob/1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def/pstack/skills/swarm/SKILL.md) for coverage matrices, races, gauntlets, and exploration partitions. Use **arena** for design or code bakeoffs with base selection and grafting.
- Contested design → the [interrogate protocol](https://github.com/cursor/plugins/blob/1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def/pstack/skills/interrogate/SKILL.md) (multi-model adversarial) before shipping.
- Nontrivial multi-step → write the throughput checkpoint (Feature step 3).
- Any prose surface, your reply to the user included → the [unslop skill](../unslop/SKILL.md). Write the reply per **Writing the reply**. Agent-facing prose also follows the [shared writing-instructions rules](references/working-rules.md#writing-agent-instructions); the [skill-authoring playbook](playbooks/authoring-a-skill.md) reports any missing native authoring workflow rather than inventing commands.
- Docs, RFCs, readmes, PR descriptions, or commit messages → the [technical-writing skill](../technical-writing/SKILL.md) (`/technical-writing`).
- Before commit → the installed [deslop skill](../deslop/SKILL.md).
- Before review → the **no-comments** skill (`/no-comments`).
- Shipping UI / IDE / CLI → the matching control skill. For terminals, use [control-cli](../control-cli/SKILL.md) and the project's proven verification skill. For UI, use the configured browser/UI workflow. For bug fixes, reproduce first on the same surface yourself. Hand to the user only under the narrow Bug fix step 1 exception.
- Running a benchmark, measuring perf yourself, or reporting a speedup or regression you measured → the [benchmark-checklist skill](../benchmark-checklist/SKILL.md) before you report or act on the number.
- Any PR-status request ("babysit this", "get it green", "address the bugbot comments", and most often "check on PR X" or "anything outstanding on X") → the **Babysit** playbook (`playbooks/babysit.md`), not another runtime's built-in babysit skill, whose description matches the same words. Never triggered by merely opening a PR. Declare its mode before polling. The playbook's step 1 owns the request-to-mode mapping. Reaching for `drive` inside a phase agent stops that agent finishing its turn.
- Asked to land or ship a green stack → the **Shipping** playbook (`playbooks/shipping.md`). Green is not safe. Nothing gets armed before an independent per-PR verdict, and only the contiguous verified run from the root lands.
- Bugbot or the agentic security review commented → skeptical posture. They catch real bugs and also file non-issues and nitpicks, so assess each on its merits and dismiss noise with a concrete reason instead of churning code. Triage fix / dismiss / ask per `references/bugbot-triage.md`.
- Broken skill mid-task → fix it in its own PR. Don't block. Don't silently work around it.
- Long, autonomous, or multi-phase work, or any task the user steps away from to review later ("going to bed", "trust it when i'm back", "/loop until X") → a decision trail via the [show-me-your-work skill](../show-me-your-work/SKILL.md). Commit it when stakes need an auditable record. Keep it local otherwise.

## Principles

Read the leaf skill in full for any principle you apply. Each entry names when it applies. Each leaf is the **principle-<title>** skill, with the title in kebab case, hyphens kept and other punctuation dropped, unless the entry gives its name.

**Core**

- **[Laziness Protocol](https://github.com/cursor/plugins/blob/1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def/pstack/skills/principle-laziness-protocol/SKILL.md).** Refactoring, sizing a diff, or tempted to add abstractions, layers, or signal threading. Bias to deletion and the smallest change that solves the problem.
- **[Foundational Thinking](https://github.com/cursor/plugins/blob/1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def/pstack/skills/principle-foundational-thinking/SKILL.md).** Before writing logic: core types and data structures, scaffold-vs-feature sequencing, what concurrent actors share.
- **[Redesign from First Principles](https://github.com/cursor/plugins/blob/1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def/pstack/skills/principle-redesign-from-first-principles/SKILL.md).** Integrating a new requirement into an existing design. Redesign as if it had been foundational from day one.
- **[Attack the Premise](https://github.com/cursor/plugins/blob/1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def/pstack/skills/principle-attack-the-premise/SKILL.md).** Two or more fixes that share one premise have failed the same gate. Take a census of which actors hold the imbalance before the next fix, then question the premise instead of writing another fix that assumes it.
- **[Subtract Before You Add](https://github.com/cursor/plugins/blob/1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def/pstack/skills/principle-subtract-before-you-add/SKILL.md).** Sequencing an addition, refactor, or rewrite. Remove dead weight first, then build on the simpler base.
- **[Minimize Reader Load](https://github.com/cursor/plugins/blob/1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def/pstack/skills/principle-minimize-reader-load/SKILL.md).** Reviewing or shaping code that's hard to trace. Count layers and hidden state, collapse one-caller wrappers, shrink mutable scope.
- **[Outcome-Oriented Execution](https://github.com/cursor/plugins/blob/1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def/pstack/skills/principle-outcome-oriented-execution/SKILL.md).** Planned rewrites and migrations with explicit phase boundaries. Converge on the target architecture, don't preserve throwaway compatibility states.
- **[Experience First](https://github.com/cursor/plugins/blob/1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def/pstack/skills/principle-experience-first/SKILL.md).** Product, UX, or feature-scope tradeoffs. Choose user delight over implementation convenience.
- **[Exhaust the Design Space](https://github.com/cursor/plugins/blob/1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def/pstack/skills/principle-exhaust-the-design-space/SKILL.md).** A novel interaction or architectural decision with no precedent. Build 2-3 competing prototypes and compare before committing.
- **[Build the Lever](https://github.com/cursor/plugins/blob/1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def/pstack/skills/principle-build-the-lever/SKILL.md).** Any non-trivial work. Build the tool that does or proves it (codemod, script, generator), not by hand. The tool is the artifact a reviewer reruns.

**Architecture**

- **[Model the Domain](https://github.com/cursor/plugins/blob/1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def/pstack/skills/principle-model-the-domain/SKILL.md).** Writing stateful logic, or code that branches a lot or repeats a shape assumption across files. Encode the domain in a structure (state machine, typed model, table or registry, reducer, boundary, the right collection) instead of scattered conditionals.
- **[Boundary Discipline](https://github.com/cursor/plugins/blob/1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def/pstack/skills/principle-boundary-discipline/SKILL.md).** Wiring validation, error handling, or framework adapters. Guards at system boundaries, trust internal types, keep business logic pure.
- **[Type System Discipline](https://github.com/cursor/plugins/blob/1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def/pstack/skills/principle-type-system-discipline/SKILL.md).** Designing types or a signature in any typed language. Make illegal states unrepresentable, brand primitives, parse external data at boundaries.
- **[Make Operations Idempotent](https://github.com/cursor/plugins/blob/1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def/pstack/skills/principle-make-operations-idempotent/SKILL.md).** Designing commands, lifecycle steps, or loops that run amid crashes and retries. Converge to the same end state.
- **[Migrate Callers Then Delete Legacy APIs](https://github.com/cursor/plugins/blob/1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def/pstack/skills/principle-migrate-callers-then-delete-legacy-apis/SKILL.md).** Introducing a new internal API while old callers exist. Migrate and delete in one wave.
- **[Separate Before Serializing Shared State](https://github.com/cursor/plugins/blob/1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def/pstack/skills/principle-separate-before-serializing-shared-state/SKILL.md).** Concurrent actors might write the same file, branch, key, or object. Eliminate the sharing first.

**Verification**

- **[Prove It Works](https://github.com/cursor/plugins/blob/1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def/pstack/skills/principle-prove-it-works/SKILL.md).** After a task, before declaring done. Verify against the real artifact, not a proxy or "it compiles".
- **[Fix Root Causes](https://github.com/cursor/plugins/blob/1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def/pstack/skills/principle-fix-root-causes/SKILL.md).** Debugging. Trace each symptom to its root cause, reproduce first, ask why until you reach it.
- **Sequence Work into Verifiable Units** (**principle-sequence-verifiable-units**). Multi-step work (sweeps, migrations, runs of similar edits) and how you stack commits and PRs. Break work into small units that each end in a check, verify each before the next, and order delivery so the sequence proves itself.
- **[Test Behavior, Not Implementation](https://github.com/cursor/plugins/blob/1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def/pstack/skills/principle-test-behavior-not-implementation/SKILL.md).** Writing, changing, or keeping a test. Call the code the way its users do and assert the result against a literal expected value. If the test would still pass when every imported function returns `undefined`, rewrite the assertion or delete the test.
- **[Explain the Number](https://github.com/cursor/plugins/blob/1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def/pstack/skills/principle-explain-the-number/SKILL.md).** Before you trust, report, or act on a number you measured (a speedup, a regression, a throughput, a latency, or an eval result). Find what limits it, and rule out that it measured something other than the work you think.

**Delegation**

- **[Guard the Context Window](https://github.com/cursor/plugins/blob/1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def/pstack/skills/principle-guard-the-context-window/SKILL.md).** Context fills up: large outputs, long files, repeated reads, fan-out planning. Route bulk to subagents, keep summaries in the main thread.
- **[Never Block on the Human](https://github.com/cursor/plugins/blob/1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def/pstack/skills/principle-never-block-on-the-human/SKILL.md).** Tempted to ask "should I do X?" on reversible work. Proceed, present the result, let the human course-correct.

**Meta**

- **[Encode Lessons in Structure](https://github.com/cursor/plugins/blob/1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def/pstack/skills/principle-encode-lessons-in-structure/SKILL.md).** You catch yourself writing the same instruction a second time. Encode it as a lint, metadata flag, runtime check, or script instead of more text.

## Autonomy

**Just do it.** Use tools available under the active permissions. Authorized reversible work proceeds without asking. External actions proceed only when the user request or standing authorization covers the action and destination.

**Always pause** for irreversible writes: rewriting shared published bookmarks, deploys, data deletion, customer messages.

**Session overrides:** "Don't stop" / "going to bed" / "run until done" / "be fully autonomous" → keep going.

**No is an acceptable answer.** Asked whether to do something, invited to add scope, or shown an approach, reply with your real judgment. Decline, push back, or say "this doesn't earn its place" when true. A recommendation is a judgment, not a validation. Agreement is not the default, candor over sycophancy.

## Subagents

**Use the configured `dav-agent` role for any subagent you spawn inside a playbook step** (code-writing delegates, ad-hoc helpers). The chat that receives `/dav-mode` runs the playbook. Never spawn a `dav-agent` to run the playbook itself. `dav-mode` supplies the parent workflow. The Claude, Codex, and Yuke `dav-agent` adapters read the canonical mode instructions. Routed workflow skills (`how`, `why`, `interrogate`, `reflect`, `swarm`) set their own `subagent_type` for diverse-model review. Respect what the skill prescribes, don't override to `dav-agent`.

**Defaults for every native child call.** Follow the harness's actual start, wait, follow-up, and stop lifecycle. Use configured agent/model roles and inherit defaults when no role-specific model exists. Code delegates tier by difficulty when those roles are available. The hardest changes go to the strongest configured judgment model; trivial mechanical edits go to the fast code model. Prose and judgment use their configured role. Do not invent per-call model fields, cloud environments, or nested depth. Routed workflows keep their own diversity requirements. An unavailable independent role or model family leaves its verification gate open. Delegation requires the user's explicit request.

You own every subagent's work. Review the diff and write your own summary, don't pass through what it said. A second opinion is the same prompt against a different model. Agreement is high-signal.

**Fresh subagents by default.** Give new work to a fresh subagent with consolidated scope, meaning the original brief, every later directive, and the prior agent's report and branch. This holds for a fix round, a follow-up, a retry, and the next queue item. Resume, message, or queue a follow-up on an existing subagent only when the new work strictly needs state that lives in that agent and is costly to move: its local checkout, its uncommitted changes, or a process it still runs, such as a dev server, a simulator, or a babysit watcher. A stop or hold order to a running agent is not reuse. A role such as a PR owner outlives its agent. Once that agent returns, a fresh agent takes the role's next round. Interrupt-chained resumes silently drop directives, so fire a fresh subagent with consolidated scope rather than trusting a "done" summary.

## Writing the reply

Write the reply clean as you draft it. A cleanup pass after drafting does not remove these patterns.

- **Short declarative sentences.** One thought per sentence, ended with a period.
- **No long-dash character anywhere.** Write a file-list bullet as a sentence ("`main.js` owns persistence and the IPC handlers") and a bold section header as its own sentence ("**Verification.** End to end via CDP").
- **A colon as a mid-sentence connector is also out** (unslop rule 14). A colon before a list is fine.
- **Terse is not an excuse to drop content.** Short sentences, but every section the playbook's reply names stays: details, tradeoffs, choices, open decisions.
- **Frame impact for the consumer and the maintainer.** Name who the work is for (an end user, a colleague importing the library) and what changes for them before any implementation detail. Then what the next engineer who owns this code inherits. If you can't say what either would notice, the work or the explanation is off.
- **Never fabricate a link, citation, or transcript reference.** Link only artifacts you produced or read this session.
- **Every claim carries its evidence or its label in the same sentence.** Measured, inferred, or guess. A prediction or an unseen cause is a guess. Never hand the human a check you could run.

Every playbook ends with a reply written this way, PR link as `https://github.com/<owner>/<repo>/pull/<number>`. Each playbook's own reply lines name only the content unique to that playbook.

## Comments

Comments follow the same rule as the reply. Write them clean as you go. Read the canonical [Comment Sicko rules](../comment-sicko/SKILL.md) for allowed categories, and [no-comments](../no-comments/SKILL.md) to verify and apply findings. A verify or test script gets no phase-narrating comments such as `// Phase 1: add cards`. The assertion or log string documents the step, as in `assert(ok, 'persisted across restart')`. This applies to every file you produce, including the delegate's diff.

## Playbooks

Open a todolist whose first items are the matched playbook's steps, copied in verbatim, before any task-specific todos. A step you choose not to do stays in the list with a one-line `skip: <reason>`. Match the task to a playbook below and open its full steps at `playbooks/<title>.md`, with the title in kebab case, hyphens kept and other punctuation dropped, using the explicit installed link below. Copy its steps in verbatim.

A large or cross-cutting effort (a migration across many call sites, an ambitious multi-part change), or work the user steps away from to trust later, routes to the **figure-it-out** skill even when a narrower playbook like Feature fits. Use **figure-it-out** whenever no bundled playbook fits. It designs a bespoke, rigorous playbook for the task. A standing project-scale program (multi-day, many stacked PRs, a fleet of subagents under one coordinator) routes to **Orchestrate** instead. figure-it-out designs one bespoke run, orchestrate runs the program.

- **[Investigation](playbooks/investigation.md).** Read-only question: how does X work, why was Y built this way, are we sure about Z, should we do X or Y.
- **[Bug fix](playbooks/bug-fix.md).** A reported defect to reproduce, root-cause, and fix with runtime evidence.
- **[Perf issue](playbooks/perf-issue.md).** A measured slowness to trace and improve against a baseline.
- **[Hillclimb](playbooks/hillclimb.md).** Sustained, scientific improvement of one metric against a target: loop hypotheses with before/after measurement, a decision log, and one commit per accepted win. Distinct from Perf issue, which is a one-off fix.
- **[Trace forensics](playbooks/trace-forensics.md).** Diagnose an existing CPU profile, trace, heap snapshot, or spindump. Query the fixed capture and cite the source location; do not re-run the capture.
- **[Runtime forensics](playbooks/runtime-forensics.md).** Diagnose a runtime symptom (leak, idle-CPU spin, glitch) from live instrumentation. The deliverable is a diagnosis, not a fix.
- **[Feature](playbooks/feature.md).** New or changed behavior, built from a named data shape.
- **[Authoring or modifying a skill](playbooks/authoring-a-skill.md).** Skill creation or edits, with native authoring and validation gates.
- **[Workspace and simulator cleanup](playbooks/worktree-cleanup.md).** Read-only jj workspace audit, usage verification, and explicitly approved state cleanup.
- **[Refactoring](playbooks/refactoring.md).** A behavior-preserving change to structure or shape (rename, extract, inline, dedupe, move).
- **[Prototype](playbooks/prototype.md).** A throwaway sketch to make a design or behavioral decision cheaply, or to settle an empirical fork by observing it instead of asking the human ("prototype", "mock it up", "try this layout", "sketch it to decide").
- **[Visual parity](playbooks/visual-parity.md).** Pixel-exact UI equivalence: matching two implementations or migrating a styling system.
- **[Eval](playbooks/eval.md).** Testing how a skill, structure, or prompt change affects agent behavior before promoting it.
- **[Babysit](playbooks/babysit.md).** Driving a PR or a stack to merge-ready: conflicts, review threads, CI.
- **[Shipping](playbooks/shipping.md).** The half after Babysit. Independently verifying a green stack, then landing the contiguous verified run bottom-up through `gh` by default or Origin when its CLI is available.
- **[Autonomous run](playbooks/autonomous-run.md).** A long task to drive to completion without stopping ("run until done", "/loop until X").
- **[Orchestrate](playbooks/orchestrate.md).** A standing project handed to one coordinator chat: multi-day, many stacked PRs, dozens to hundreds of subagents, minimal human turns ("run this whole project", "own this migration until it lands"). Distinct from Autonomous run, which drives one task to a predicate. Work one agent could finish inside the session's budget routes there, not here, however program-shaped the phrasing sounds.
- **[Autopilot-full](playbooks/autopilot-full.md).** A queue of independent PRs run to merged with full autonomy. One owner per PR carries build through merge, and the root swarm-verifies each PR before its owner merges ("autopilot this queue", "full autopilot", one-owner-per-PR programs).
- **[Autopilot-stack](playbooks/autopilot-stack.md).** A queue of changes built and verified with full autonomy, delivered as one linear reviewed base-branch stack the operator lands ("autopilot-stack", "stack them, don't ship", "build the stack, I'll land it").
- **[Session pickup](playbooks/session-pickup.md).** Resuming or taking over a prior agent's in-flight work from a transcript, remote-agent URL, or pushed branch.
- **[Pause safely](playbooks/pause-safely.md).** Suspending in-flight work cleanly so it can be resumed, on an explicit pause, going offline, a runtime restart, or imminent context compaction. The complement to Session pickup.
- **[Multi-phase or multi-PR plan](playbooks/multi-phase-plan.md).** Work that spans phases or stacked PRs. File: `playbooks/multi-phase-plan.md`.
- **[Opening a PR](playbooks/opening-a-pr.md).** Invoked at the end of every other playbook.
