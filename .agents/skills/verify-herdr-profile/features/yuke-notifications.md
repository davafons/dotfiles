# Yuke registration and question notifications

## Sub-features

Registration, blocked/idle transitions, single and batch questions, session isolation, silent notifications, reload, and quit release.

## How to get to it (user POV)

Start Yuke inside a Herdr pane. A pending clarification appears in the Herdr notification list while the agent reports blocked. Answering or dismissing it returns the expected state.

## Driving it with the repository driver

Run `python3 -B yuke/tests/check-herdr.py --binary "$(command -v yuke)" 2>&1 | tee "$EVIDENCE/yuke-notifications.log"`. Require explicit PASS lines and read the printed artifact directory with `result.json`, `captures.txt`, and `notification-screen.txt`.

## Gotchas

The guard uses private Herdr and Yuke state and explicitly disables sound. Fixture questions are not approvals for real operations. No paid model calls or user-session reload occurs.
