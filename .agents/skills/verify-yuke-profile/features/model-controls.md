# Model controls and aliases

## Sub-features

Model and effort pickers, aliases and their editor, alias store revisions, and the `startupModel` and `startupEffort` options in `config.json`.

## How to get to it (user POV)

Use Ctrl+X M for the model picker and Ctrl+X E for effort. `/model-aliases` edits the aliases. Each alias adds its own `/<alias>` command and key.

## Driving it with the repository driver

Run `python3 -B -m unittest -v yuke-rust/tests/test_model_alias_store.py 2>&1 | tee "$EVIDENCE/models.log"` for the store, and the terminal driver in [composer-reload](composer-reload.md) for the picker UI. Require every test to pass.

## Gotchas

The live aliases are state in `~/.local/share/yuke-rust/plugins/models/model-aliases.json`; `yuke-rust/state/model-aliases.json` only seeds a new machine. Do not edit the live file in a verification run.
