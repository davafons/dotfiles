# Source and modifications

This directory includes the complete public Anthropic skill-creator at
`dbd4588f9e1033efb41dad4bef2f7947c8993d44`, licensed under Apache-2.0 in `LICENSE.txt`.
It is not Cursor's unpublished built-in `create-skill`.

Modified upstream files for native execution and authority boundaries:

- `SKILL.md`.
- `eval-viewer/generate_review.py`.
- `scripts/run_eval.py`.
- `scripts/improve_description.py`.
- `scripts/run_loop.py`.

Added `scripts/native_model.py` and `references/native-runtime.md`.
All grader/comparator/analyzer prompts, JSON schemas, HTML assets, packaging
helpers, and statistics/report algorithms are retained. Native worker errors
abort scoring rather than become false nontriggers. The static viewer is the
default instruction, and serving never kills another process by port.
