---
name: verify-herdr-profile
description: "Drive the dotfiles Herdr integrations in private sessions. Use after changing indexed shortcuts, Code-tab ordering, or Yuke registration and clarification notifications."
---

# Verify Herdr profile

## Launch

From the dotfiles root, prepare silent fixture sources:

```sh
set -eu
set -o pipefail
DOTFILES_ROOT="$PWD"
EVIDENCE="$(mktemp -d "${TMPDIR:-/tmp}/verify-herdr-profile.XXXXXX")"
python3 -B .agents/skills/verify-herdr-profile/scripts/prepare.py "$EVIDENCE"
HERDR_GUARDS="$EVIDENCE/staged-herdr/local-plugins"
printf '%s\n' "$EVIDENCE"
```

The preparation helper copies checked-in local plugin sources without build
output. It disables sound and automatic agent restoration in staged config.
Every driver selects a unique `--session`, removes inherited `HERDR_*` routing,
and controls only that server. Do not substitute commands targeting the normal
Herdr session. Each drive creates and tears down its own instance.

## Doctor

```sh
herdr --version | tee "$EVIDENCE/version.log"
command -v tmux
command -v python3
python3 -c 'import tomllib'
test -f "$HERDR_GUARDS/code/tests/check-code-order.py"
test -f "$HERDR_GUARDS/sidebar-numbers/tests/check-shortcuts.py"
```

For the Yuke integration also require `yuke --version`. If a drive surprises you,
inspect its owned server log and rerun Doctor before starting another instance.
Never use a normal-session status or focused pane as a health check for a test.

## Drive

Start with Code-tab order and workspace identity:

```sh
HERDR_CODE_TEST_ARTIFACT="$EVIDENCE/code-order.json" \
  python3 -B "$HERDR_GUARDS/code/tests/check-code-order.py" \
  2>&1 | tee "$EVIDENCE/drive.log"
```

Require the artifact's `ok` and `server_stopped` to be true. Read its native
`final_snapshot`, plugin logs, and order/identity results. This drive uses fixture
editor records to test real Herdr hooks. It does not launch or prove the full
Neovim Code editor. Do not turn its result into a claim about editor rendering.

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
