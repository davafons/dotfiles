# Yuke registration and question notifications

## Sub-features

Registration, blocked/idle transitions, single and batch questions, session isolation, silent notifications, reload, and quit release.

## How to get to it (user POV)

Start Yuke inside a Herdr pane. A pending clarification appears in the Herdr notification list while the agent reports blocked. Answering or dismissing it returns the expected state.

## Driving it with the repository driver

Run `YUKE_BINARY="$HOME/.local/lib/yuke-rust/bin/yuke" python3 -B -m unittest -v yuke-rust/tests/test_herdr.py 2>&1 | tee "$EVIDENCE/yuke-notifications.log"` and `"$HOME/.local/lib/yuke-rust/bin/yuke" test yuke-rust/scripts/herdr.test.ts 2>&1 | tee -a "$EVIDENCE/yuke-notifications.log"`. Require every test to pass. These cover the framed Herdr transport and pane state. Check question notifications by hand in a real Herdr pane: ask a fixture question and confirm it appears and clears.

## Gotchas

The guard uses private Herdr and Yuke state and explicitly disables sound. Fixture questions are not approvals for real operations. No paid model calls or user-session reload occurs.
