---
name: verify-yuke-profile
description: "Drive the dotfiles yuke-rust profile in isolated terminals. Use after changing profile plugins, composer input, model controls, status rendering, or reload behavior."
---

# Verify Yuke profile

The profile is `yuke-rust/.config/yuke-rust`. Stow links it into `~/.config/yuke-rust`.
Every driver below copies the profile from this checkout into a private home, so it never
touches the user's live profile, sessions, or credentials.

## Launch

From the dotfiles root, create evidence and select the binary:

```sh
set -eu
set -o pipefail
YUKE_BIN="$HOME/.local/lib/yuke-rust/bin/yuke"
YUKE_SOURCE="$HOME/workspace/yuke"
EVIDENCE="$(mktemp -d "${TMPDIR:-/tmp}/verify-yuke-profile.XXXXXX")"
printf '%s\n' "$EVIDENCE"
```

To check a candidate build before installing it, set `YUKE_BIN` to its
`target/release/yuke` instead. Use the SDK and source of that same build.

## Doctor

```sh
"$YUKE_BIN" --version | tee "$EVIDENCE/version.log"
test -f "$HOME/.local/lib/yuke-rust/tsconfig.json"
git -C "$YUKE_SOURCE" log -1 --oneline | tee "$EVIDENCE/source.log"
```

Do not run `/reload` or plugin commands in the user's real session as part of verification.

## Drive

Run the whole profile check first:

```sh
python3 -B yuke-rust/scripts/verify.py --source "$YUKE_SOURCE" --binary "$YUKE_BIN" \
  2>&1 | tee "$EVIDENCE/verify.log"
```

Require a `PASS` line for every stage: profile-types, profile-biome, profile-tools, vim,
stores, terminal, and agent-tools. On a failure, the script prints the stage's log path under
`$YUKE_SOURCE/target/migration-verification`; keep it. Add `--native` after a native source change.

Use the [feature map](features/README.md) to drive one area on its own.

## Evidence

Keep each drive in its own fresh directory outside the checkout. Capture the exact command,
the source revision, stdout, stderr, exit status, and any artifact directory a driver prints.
A zero exit without the driver's explicit `PASS` lines is not proof.

The scripted local providers prove routing and integration, not real model quality, external
credentials, or provider behavior.

## Cleanup

Each driver owns its private process teardown. Never kill by process name or stop the user's
Herdr, tmux, Neovim, or Yuke session. Keep the evidence directory after failures too.
These drives use background PTYs. They do not use the clipboard, play audio, or activate a desktop app.

## Helpers

Use the existing drivers. Do not create a competing harness. Read a driver before running it
after source changes. Do not copy `auth.json`, `monid.key`, or other credentials into test profiles.
