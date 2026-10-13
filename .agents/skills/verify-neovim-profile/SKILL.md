---
name: verify-neovim-profile
description: "Drive the dotfiles Neovim configuration with its existing private PTY and headless probes. Use after changing completion, project pickers, CodeDiff review, or Markdown rendering."
---

# Verify Neovim profile

## Launch

From the dotfiles root, select the installed runtime and retain proof:

```sh
set -eu
set -o pipefail
DOTFILES_ROOT="$PWD"
NVIM_CONFIG="$DOTFILES_ROOT/nvim/.config/nvim"
NVIM_DATA="${XDG_DATA_HOME:-$HOME/.local/share}/nvim/personal"
EVIDENCE="$(mktemp -d "${TMPDIR:-/tmp}/verify-neovim-profile.XXXXXX")"
printf '%s\n' "$EVIDENCE"
```

The drivers reuse installed pinned plugins and create temporary source files,
config links, caches, and editor state. They launch a fresh background PTY or
headless instance per drive. They never attach to an existing editor. Missing
plugins are a blocker; do not let verification install or update plugins.

## Doctor

```sh
nvim --version | head -n 3 | tee "$EVIDENCE/version.log"
command -v jj
command -v fzf
command -v rg
python3 - "$NVIM_CONFIG" "$NVIM_DATA" <<'PYDOCTOR'
import json, sys
from pathlib import Path
config, data = map(Path, sys.argv[1:])
locked = json.loads((config / 'lazy-lock.json').read_text())
missing = [name for name in locked if not (data / 'lazy' / name).is_dir()]
assert not missing, 'Missing installed plugins: ' + ', '.join(missing)
assert (data / 'lazy/lazy.nvim').is_dir(), 'Missing lazy.nvim'
assert list((data / 'lazy/blink.cmp').rglob('libblink_cmp_fuzzy*')), 'Missing blink native library'
assert list((data / 'lazy/codediff.nvim').rglob('libvscode_diff*')), 'Missing CodeDiff native library'
print('Installed plugin prerequisites present')
PYDOCTOR
```

Doctor checks availability, not behavior or every installed revision. The drives
exercise the actual installed plugins. After failure, read the captured stderr,
rerun Doctor, and start a fresh drive rather than reusing a wedged editor.

## Drive

Start with project pickers and completion:

```sh
python3 -B "$NVIM_CONFIG/tests/check-config.py" \
  2>&1 | tee "$EVIDENCE/drive.log"
```

Require `Neovim config checks passed` with config, completion, pickers, and
unsaved-edits results. The guard exercises real command-line completion and
picker selection. Source files must remain unchanged on disk after cleanup.

## Evidence

Keep each drive in its own fresh directory outside the checkout. Capture the
exact command, source revision, stdout, stderr, exit status, and any driver-owned
artifact path. Use `set -o pipefail` when piping a drive through `tee`.
A zero exit without the driver's explicit completion report is not proof.

The feature map names the required entry points. One successful mapped feature
proves generation, not complete feature coverage. For maintenance, drive every
mapped feature. Native fixture providers prove local integration, not real model
quality, external credentials, or provider routing.

## Cleanup

Each driver owns its private process/session teardown. It must finish before
another drive starts. On failure, inspect that drive's saved logs and confirm
its owned processes stopped before retrying. Never kill by process name or stop
the user's Herdr, tmux, Neovim, or Yuke session. Retain the evidence directory,
including after failures. Confirm `drive.log` and any named artifacts still exist.

Native GUI activation and system-wide input require permission for that run.
These drives use background PTYs, detached private tmux, or headless Neovim.
They do not use the clipboard or play test audio. Do not activate a desktop app.

## Helpers

Use the repository's existing drivers below. Do not create a competing harness.
Read a driver before running it after source changes. Do not copy provider files
or credentials into test profiles. Paths below are relative to the dotfiles root.

See [the feature map](features/README.md) for other drives.
