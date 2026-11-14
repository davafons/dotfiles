# Schedule prompts in one session

The `loop` plugin provides `/loop` and the model tool `loop`. Its entry is `"./plugins/loop"` in `config.json`.

Start a saved conversation before arming a loop. Use an explicit interval and an exit condition:

```text
/loop 5m Check the requested local tests. Stop this loop when they pass. Do not push or deploy.
/loop list
/loop stop
/loop stop <id>
```

Intervals use `s`, `m`, `h`, or `d`, such as `30s`, `5m`, or `1h`. The interval must be 1 to 2147483 seconds. A prompt is at most 16000 characters. `/loop` without arguments also lists loops. Results appear as notices.

Each tick says that it comes from an earlier authorized request and grants no new permission. It tells the agent to check the exit condition, stop the loop when it is met, and report a missing permission or capability. It uses the current conversation and its task records to resume.

## Timing

The first tick waits one full interval. A running turn, queued input, or unsent draft in that session postpones delivery. The loop then retries after the interval or 10 seconds, whichever is shorter. Missed ticks do not form a queue. Each tick goes to the session that armed it. Switching panes does not move the schedule.

## The model tool

The tool accepts `action` as `arm`, `list`, or `stop`. Arm also needs integer `seconds` and a nonempty `prompt`. Stop accepts an optional `id`. Without `id`, it stops every loop of the calling session. Tool calls act only on their calling session.

The agent should arm a loop only when the user requests recurrence. Arming grants no new write, delegation, push, deployment, or desktop permission.

Arming the same prompt and interval again returns the existing loop.

## Pause and stop

A failed or cancelled turn pauses every loop of the session. A failed delivery or a removed queued tick pauses its own loop. A paused loop does not deliver. Stop it before arming the same prompt and interval again.

Stop removes future timers and cancels a queued tick that this loop owns. It does not interrupt an active turn or remove other input. A tick from a stopped or paused loop is dropped before it reaches the model.

Closing the session, quitting, and `/reload` stop all loops. A loop has no saved schedule. Startup never restores loops.

## Checks

```sh
python3 ~/dotfiles/yuke-rust/scripts/verify.py --source ~/workspace/yuke --binary ~/.local/lib/yuke-rust/bin/yuke
```

`tests/tools.test.ts` arms a one-second loop through the tool in a test host. It checks that the tick reaches its owning session once and that stop ends it. It uses a fixture reply, not a real provider.

No test covers `/loop` in a real terminal, pause after a failed or cancelled turn, or cleanup on reload.
