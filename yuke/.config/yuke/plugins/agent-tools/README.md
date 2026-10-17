# Child tools

`spawn_agent` selects one configured role. `send_agent_input` addresses a direct
child that already exists. The native engine owns runs, reports, depth limits,
and stopping. Delegate only when the user explicitly requests it.

| Role | Model | Reasoning |
| --- | --- | --- |
| `general`, including an omitted role | `openai-codex/gpt-6-luna` | Model default |
| `dav-agent` | Parent model | Parent reasoning |
| `reviewer` | `openai-codex/gpt-6.1-sol` | `xhigh` |

This batch selects GPT-6.1 Sol, the latest Sol in the captured native catalog.
Its larger context window and supported xhigh setting suit scoped review.
The role stays pinned to that selector; it does not auto-upgrade. This
is a configuration choice, not a measured claim that it beats every other model.
Existing coding roles are unchanged. No other provider or credential is added.

Give a reviewer the exact changed paths, base revision, retained test evidence,
and required verdict. Use a fresh non-author context. Review-only is a task
constraint, not a security sandbox. A reviewer still has the host's permissions.
A different role, GPT version, or fresh session does not prove family diversity.
The current Codex-only choice leaves cross-family gates open.

The spawn tool's saved output includes an `Engine model receipt` with child and
session IDs, role, parent model, accepted model, and reasoning. Child request
hooks write `CHILD_REQUEST_MODEL` to that process's Yuke log. These are engine
settings, not a model's self-reported identity. Later hooks can change a request;
inspect actual request evidence when a model-specific gate matters. Do not infer
provider execution or review quality from configuration alone.

Run the native plumbing guard from the dotfiles root:

```sh
python3 -B yuke/tests/check-agent-tools.py --binary "$(command -v yuke)"
```

It uses private homes, profile/state/data directories, and a scripted localhost
provider. It invokes the real spawn tool, reads actual parent/child histories and
stored settings, and checks HTTP model/effort payloads, depth-limit tools, and
native project-skill discovery. The printed evidence directory survives process
and provider teardown. No real model calls or real reviews occur. The fixture
route preserves both endpoint protocols needed by the baked Codex catalog.

The project [verification skill](../../../../../.agents/skills/verify-yuke-profile/SKILL.md)
contains the maintained feature map. Install only intentional source changes
into the copied profile. Wait for active runs to finish, save the typed draft,
and perform an idle `/reload` or restart before expecting the new tool role.
Starting another chat inside an old process does not reload the plugin. Do not
reload the user's current session just to verify this change.

## Bounded private campaigns

The native authoring runner can opt a fresh process into a prepaid quota through
`DAVSTACK_CAMPAIGN`. Ordinary sessions without that variable keep their existing
behavior. The public child-tool arguments and configured roles do not change.
The runner reserves the entire process quota, including its root, before launch.
Failed and unused reservations remain consumed.

In campaign mode, child creation takes a slot before calling the engine and sets
`max_rounds=8`. A session map also caps requests across resumed turns. Only one
root and one child level are allowed. The guard restricts tools to private-workspace
file operations, child dispatch, follow-up and stop. Shell and MCP tools are absent
and refused. The runner owns the process deadline and teardown. This is not a
general sandbox against malicious profile plugins or arbitrary untrusted prompts.

After registering the tools and hooks, the guard writes a nonce acknowledgment
into the private cache. The runner refuses to send input unless it matches the
grant. A missing or failed plugin therefore cannot silently start an uncapped run.
The native application reads its existing provider account; no provider files or
credentials are copied. Installing this source does not reload an active session.
