# Model controls and effort

## Sub-features

Model picker/aliases, accepted effort, saved-session settings, stale metadata protection, and configurable switches.

## How to get to it (user POV)

Use Ctrl+X M for model selection and Ctrl+X E for effort. A configured alias can select its model without opening the picker.

## Driving it with the repository driver

Run `python3 -B yuke/tests/check-plugin-groups.py --binary "$YUKE_BIN" --group models 2>&1 | tee "$EVIDENCE/models.log"`. Require every selected variant and invalid-settings rejection to PASS. Keep the printed artifact directory.

## Gotchas

The fixture model is `group-test/model` on localhost port 1. It proves settings persistence and UI integration, not paid provider execution or cross-family review.
