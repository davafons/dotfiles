---
name: loop
description: Schedule repeated agent turns for an explicitly authorized task. Use for /loop, recurring checks, or an autonomous task that needs a real timer. Requires a native scheduler; a shell loop is not a replacement.
---

# Loop

Read the [shared working rules](../dav-mode/references/working-rules.md) and the task's full [dav-mode playbook](../dav-mode/SKILL.md).
This is a local runtime adapter for the upstream execution playbooks. Upstream `/loop` is a Cursor built-in, not a pstack skill.

1. State the goal, scope, and falsifiable exit condition. Use `until stopped` only when the operator requested ongoing monitoring. A request to write a plan or install this skill does not authorize recurring execution.
2. Identify the actual scheduler and its lifetime. A prompt file supplies no timer. A foreground shell loop runs commands, not fresh agent turns. If the runtime has no supported scheduler, report the gap and leave the schedule unarmed.
3. Choose a cadence based on when another result is worth checking. A native watcher can wake the parent when it has a result. Use a slower heartbeat as a backstop. Do not add frequent model turns while a watcher is still waiting.
4. Arm only on the operator's explicit go. Save the returned loop ID, interval, prompt, and lifetime in the task's decision trail. Keep all existing permission and ownership limits. Scheduling grants no delegation, external posting, push, merge, deploy, data deletion, or desktop authority.
5. At each tick, re-read the governing playbook and current operator constraints. Check the exit condition before taking action. Inspect actual artifacts and side effects. A green CI run, a summary, or a scheduled timer is not an independent verdict.
6. Disarm on the exit condition, an operator hold, an unmet permission, or a runtime capability that prevents progress. Save a checkpoint with the actual result and remaining gaps. Do not report the task complete merely because its timer stopped.

## Yuke

The profile's `session-loop` plugin supplies the `/loop` command and `loop` model tool. It starts no schedules at installation or startup.

```text
/loop 5m Check PR 123 under Babysit check mode. Stop at merge-ready. Do not merge.
/loop list
/loop stop <loop-id>
/loop stop
```

Use a saved conversation. The first tick waits one interval. The plugin sends the prompt through `client.sessionSendInput` into that same session. It defers while the session is busy, has queued input, or has an unsent composer draft. Missed ticks collapse into one pending check. Identical arm requests reuse an existing active loop.

The `loop` tool takes `action: "arm"` with `seconds` and `prompt`, `action: "list"`, or `action: "stop"` with an optional `id`. Omitting the ID stops all loops in the calling session, not other sessions.

Schedules exist only in the loaded plugin. Quit or profile reload stops them. Nothing runs while Yuke is closed. Restart or reload requires explicit rearming. There is no daemon or saved schedule. Delivery errors pause the loop. A reported failed or canceled terminal outcome can also pause it; the SDK does not expose every terminal outcome for every session.

Stop cancels future ticks and only the loop's own queued input. It does not cancel an already-running turn or clear unrelated user input. Use the normal interruption control for an active turn. On a hard process kill, cleanup cannot retract an input the engine already admitted. Do not describe the process-local timer as durable execution.

## Other runtimes

Use an exposed, supported native scheduler when one exists. Record its actual lifetime and stop mechanism. Cursor's built-in `/loop` is a separate implementation. This installation supplies no Claude or Codex scheduler adapter. If those runtimes cannot expose one, keep their scheduling gate open. Do not claim that sharing this skill made the timer portable.
