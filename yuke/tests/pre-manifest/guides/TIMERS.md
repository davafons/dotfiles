# Per-step timers

`plugins/step-timers.js` is enabled in the user profile.

- Each tool header has a right-aligned live timer. `not started` measures the wait before dispatch, not command execution. `running` measures the tool pipeline from the engine's start timestamp (including hooks).
- Tool completion keeps the engine's final duration. Errors and cancellation retain their state. The old `Took Xs` metadata footer is hidden; command output is unchanged.
- Each reasoning block has a live timer, including blocks whose provider hides the text. Completed blocks use the engine's duration.
- `plugins/phase-timers.js` shows the last three model phases above the prompt rule. It labels each phase with `request` or the preceding tool. Waiting, responding, reasoning, retry, preparation, and compaction have separate clocks. Completed phases keep their time until the next run.
- Queued user messages remain visible. They are separate from tool calls marked `not started`.

Phase and pending-tool clocks start when this profile observes them. Reloading during a run cannot recover earlier phase timing. The provider does not expose the content of hidden reasoning. Historical tool and thought durations use engine metadata where available.

Timers update every 100 ms while work is active. They request no idle timer pulses. The display does not change the model's transcript or copy source.

Restart yuke to load the profile. This profile's custom `/reload` also reloads these plugins.

## Check

```sh
python3 ~/.config/yuke/tests/check-step-timers.py
python3 ~/.config/yuke/tests/check-step-trace.py
yuke check
```

The focused test uses a detached tmux session with an isolated profile and session store. It makes no model requests, uses no desktop input, and does not access the clipboard. It checks silent live steps, hidden thoughts, final durations, errors, cancellation, phase transitions, queue preservation, copy source, narrow terminals, unload, and the duplicate duration footer.

## Diagnostic logs

`step-trace.js` writes timestamped JSON lines prefixed with `STEP_TRACE` to `~/.local/state/yuke/yuke.log`. It records:

- Tool states, keyed by session, message, and part. A pending call has no execution start.
- The `tool.before` and `tool.after` hook boundaries. The after hook exposes no session ID, so its record uses an argument fingerprint, not an invented session match.
- Phase changes and queued-input counts.
- Cancellation request and resolution/rejection times.
- A report every 30 seconds while a call remains unresolved, and gaps in the diagnostic heartbeat.

Argument fingerprints are non-cryptographic correlation IDs. Logs do not contain tool arguments, commands, output, reasoning, or credentials. Heartbeat gaps can indicate event-loop delay, suspension, or a wall-clock change; they do not identify which one. No diagnostic timer runs when all observed calls have settled. Reload captures already-open tool calls, but cannot recover their earlier pending start time.

To inspect the added records:

```sh
grep 'STEP_TRACE ' ~/.local/state/yuke/yuke.log
```
