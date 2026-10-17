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

- **Execute the smallest useful case first.** Plan only enough to perform the
  next concrete check. Add infrastructure only when an observed blocker requires
  it. Once the acceptance check passes, move directly to execution or handoff.
  Reopen planning only when new evidence changes the decision. If prerequisite
  work exceeds five minutes without exercising the target behavior, report the
  blocker and remaining work. Never relax safety or permission gates to meet a
  timebox.
The locally installed [principle leaves](../SKILL.md#principles) own the
engineering methods. Read the relevant leaf rather than substituting a local
summary. The execution rule above is an explicit local user-approved addition.

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

Upstream owns the reusable methods; the [principles index](../SKILL.md#principles)
links their complete local sources. Native runtime and authority mappings live
in [Playbook runtime](playbook-runtime.md). Project architecture, commands,
state locations and ownership facts stay in the project's instructions. Keep
one canonical source instead of copying a second policy here.

## Writing agent instructions

An unhelpful sentence in an agent-facing file becomes an instruction. Tell the
agent to do the thing and skip the reason; explain only where the rule is
confusing without one. Point at the structural source rather than copying a
detail out of it. Link another skill by path instead of restating its rules.
A line earns its keep by changing a decision. Validate metadata and local links
mechanically rather than checking those by eye.

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
