# Schedule prompts in one session

The manifest plugin in `.config/yuke/plugins/loop` provides `/loop` and the model tool `loop`. It requires the native `client.sessionLastRun` API. It does not work with the earlier installed migration binary until you install a verified newer build.

Start a saved conversation before arming a loop. Use an explicit interval and an exit condition:

```text
/loop 5m Check the requested local tests. Stop this loop when they pass. Do not push or deploy.
/loop list
/loop stop
/loop stop <id>
```

The first tick waits one full interval. A busy session or unsent draft postpones delivery. Missed ticks coalesce rather than form a queue. Each tick goes to the session that armed it. Switching panes does not move the schedule.

The model tool accepts `action` as `arm`, `list`, or `stop`. Arm also needs integer `seconds` and nonempty `prompt`. Stop accepts an optional `id`. Tool calls act only on their calling session. The operator must explicitly authorize scheduled turns before the agent arms a schedule. Arming grants no new write, delegation, push, deployment, or desktop permission.

Failed delivery and failed or canceled turns pause the schedule. Stop the paused schedule before rearming it. Stop removes future timers and cancels only a queued input that this schedule owns. It does not interrupt an active turn or remove unrelated user input. Quit and native `/reload` dispose schedules. Startup never restores them.

The status bar reads cached counts. It does not construct job snapshots during drawing. Native run-outcome reads occur only after completion events while schedules exist.

## Verify it

```sh
bun test yuke/tests/loop-core.test.ts
python3 -B yuke/tests/check-loop.py --binary /absolute/path/to/verified/yuke
```

The native guard uses private directories, a detached terminal, and a loopback provider. It proves headless tool availability, scheduled delivery, cancellation pause, explicit stop, rearm, and cleanup through actual native reload. It does not arm a schedule in your normal profile or use real credentials.
