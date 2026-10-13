---
name: verify-yuke-profile
description: "Drive the dotfiles Yuke profile in isolated terminals. Use after changing profile plugins, composer input, model controls, status rendering, or reload behavior."
---

# Verify Yuke profile

## Launch

From the dotfiles root, create evidence and select the installed release:

```sh
set -eu
set -o pipefail
DOTFILES_ROOT="$PWD"
YUKE_BIN="$(command -v yuke)"
YUKE_TYPES="$HOME/.local/lib/yuke/types"
EVIDENCE="$(mktemp -d "${TMPDIR:-/tmp}/verify-yuke-profile.XXXXXX")"
printf '%s\n' "$EVIDENCE"
```

The full-profile driver needs working `tsc`. If the mise shim has no selected
version, use the already-installed TypeScript for this shell only:

```sh
TSC_ROOT="$(mise where npm:typescript@7.0.2)"
PATH="$TSC_ROOT/bin:$PATH"
export PATH
```

Do not install a compiler or change global mise settings as part of verification.
`check-profile.py` copies the manifest into fresh homes and runs both logical and
display motion variants. Other drives create their own private profiles. No
long-lived server is shared between drives.

## Doctor

```sh
"$YUKE_BIN" --version | tee "$EVIDENCE/version.log"
test -f "$YUKE_TYPES/yuke.d.ts"
test -f "$YUKE_TYPES/yuke-modules.d.ts"
tsc --version | tee "$EVIDENCE/typescript.log"
python3 -B yuke/tests/check-profile.py --help > "$EVIDENCE/driver-help.log"
```

Use declarations from the same installed build. Do not run `yuke check` in the
normal profile. After a surprising drive, rerun Doctor and inspect that drive's
private log before launching a fresh drive.

## Drive

Start with the composer and reload feature:

```sh
python3 -B yuke/tests/check-profile.py --binary "$YUKE_BIN" \
  --types-dir "$YUKE_TYPES" --output "$EVIDENCE/profile" \
  2>&1 | tee "$EVIDENCE/drive.log"
```

Require both variants to report input, native reload, disposal, and headless
success. Retain `profile/{logical,display}/terminal.raw`, `terminal.log`, and
`headless.log`. The driver presses Ctrl+G only in its own PTY, not your session.

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
