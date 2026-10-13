# Build label and status dialog

## Sub-features

Compact native build label, status details, draft preservation, and version identity across reload.

## How to get to it (user POV)

Read the bottom bar, open `/status`, select its details, close it, and reload in an idle private session.

## Driving it with the repository driver

Run `python3 -B yuke/tests/check-build-status.py --binary "$YUKE_BIN" 2>&1 | tee "$EVIDENCE/build-status.log"`. Require its explicit PASS. Keep the printed directory with `screens.txt` and `initialize.jsonl`.

## Gotchas

This guard requires a timestamped local development build. A release build is a prerequisite mismatch, not a failed compact-label fix. The fake PATH executable must not influence the running build label.
