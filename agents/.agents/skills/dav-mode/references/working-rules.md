# Shared working rules

These apply to davstack's personal skills and playbooks. User, runtime, and
project instructions take precedence. Do not expand the user's requested scope.
Read the project's AGENTS.md for architecture, commands, test configuration,
document layout, deployment boundaries, and ownership conventions. Never assume
Shirabe's Rails tools or plan format exist in another project.

## Decisions and authority

- **Proceed on authorised, reversible work.** Do the work and show the result;
  do not ask for approval of each implementation step. This does not authorise
  scope expansion, delegation, native GUI automation, deployment, or external
  communications. Respect explicit proposal-and-approval gates in a skill.
- **Classify a question before you ask it.** If the answer is observable by
  running something safely, run it. Reserve clarification for a product or
  preference call no experiment can settle, or a required authorisation. Do not
  guess a missing decision or treat a queued question as approval.
- **No is an acceptable answer.** Give your real judgment. A recommendation is
  not validation, and agreement is not the default. Do not bias a reviewer by
  telling it the existing artifact is probably good.
- **Guard the context window.** Read what you will use. Prefer targeted CLI/API
  queries and saved artifacts to bulk dumps. Delegate only when the user
  explicitly requests delegation, a subagent, or parallel work. Otherwise run
  the lenses serially and do not claim independent review.

## Changes and proof

- **The best part is no part.** Subtract before adding. Build the simplest thing
  that works, then let reality push; do not speculate. Extract on the fourth
  occurrence, not the first, unless a real boundary already earns its place.
- **Fix root causes, not symptoms.** Read the surrounding code first. Rename,
  extract, or reshape our own confusing code rather than explain it with prose.
- **Minimise reader load.** A new reader should be able to tell where a value
  comes from and what can change it. Name the invariant at its owning boundary.
- **Prove it works.** Run the real artifact and inspect the actual value. Watch
  a regression check fail without the fix when practical. Compilation, a proxy,
  and your own summary are not evidence. Report gaps and inconclusive results.
- **Build the lever.** For substantial repeatable work, build the script, task,
  or check instead of doing it by hand. It must exist and be rerunnable before
  you claim to have built it.
- **Preserve shared work.** Inspect the current diff and file state before a
  sweep or history edit. Give each mutable plan/file one owner. Revert only your
  own changes, never reset another worker's edits. In a shared jj checkout the
  working copy is already a commit; do not describe everybody's work together
  just to pause.
- **Use the repository's version-control tool.** Check for `.jj/` before version
  commands. In colocated repositories use jj, with `jj diff --git` for diffs;
  never mutate Git there. Read-only Git plumbing is only a fallback where jj has
  no equivalent. Otherwise use Git. Follow the user's branch and push workflow;
  an example in a skill does not override it.

## Where a rule lives

A rule you have to remember is the weakest guard. Put it on the strongest rung
available:

1. **Impossible to express:** no such API, or a database constraint rejecting it.
2. **Fails CI:** a lint, test, or behaviour ratchet.
3. **A canonical helper:** one implementation all callers use.
4. **A runtime check:** refuses to proceed with a broken precondition.
5. **Prose:** judgment a machine cannot make, or a measured dead end worth not
   repeating. Explain why a stronger rung does not apply.

A rule has one owner. Project facts stay with their project; reusable personal
workflows stay in davstack. A plan is a current resume snapshot, not a second
permanent home or a diary. Promote durable facts, then retire the plan according
to the project's conventions. Version control is the archive.

## Shared-desktop and external-state safety

Follow the user's shared-desktop restrictions even when a playbook calls for a
live observation. Prefer APIs, CLIs, background interactions, and saved
artifacts. Browser work uses the configured browser skill's owned session and
tabs, never the user's tabs or system-wide input. Native GUI activation,
workspace switching, and system-wide input require explicit permission for that
run. Agent-owned test windows belong on the authorised test workspace. Preserve
the clipboard; do not play test audio without audible-testing permission.
If safe live proof is blocked, continue independent work and report the gap.

Production changes, irreversible actions, sending external communications, and
deployment require the applicable user authorisation. A request for diagnosis,
investigation, or comment review is not permission to edit or ship.
