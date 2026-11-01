# dotfiles

Personal configuration deployed with [GNU Stow](https://www.gnu.org/software/stow/).

## Installing

Each machine is declared by one explicit profile manifest in `profiles/`. A
profile is an allowlist: only its listed packages are linked into the home
directory. Package variants such as `git-work` are selected by the profile;
there is no hostname-based package replacement.

```sh
git clone https://github.com/davafons/dotfiles
cd dotfiles
jj git init --colocate
make list-profiles
make plan PROFILE=mb
make install PROFILE=mb
```

Neovim is tracked directly in `nvim/.config/nvim`; no submodule setup is needed.
Its [configuration guide](nvim/.config/nvim/README.md) covers shortcuts and checks.
After initializing the colocated repository, use `jj` for version-control operations.

The [Karakeep MCP setup](bin/KARAKEEP.md) covers credentials and registration
with Claude Code and Codex on the Mac and Tower.

`make` defaults `PROFILE` to the current hostname for compatibility. Specify
`PROFILE` explicitly on a new machine.

Useful commands:

```sh
make doctor PROFILE=mb
make status PROFILE=mb
make install PROFILE=work
make install PACKAGES="shell git jj" PROFILE=mb
```

## Tower SSH auto-wake

Use `ssh tower-wake` to wake Tower and connect. This explicit alias uses
`~/bin/tower-ssh-proxy`. If SSH is unreachable, the helper sends the Home
Assistant wake webhook and waits up to 90 seconds before connecting. It
prefers the LAN and falls back to Tailscale.
SSH checks Tower's pinned host key and authenticates normally.
The LAN and Tailscale endpoints currently present the same host key.

Install the `bin` and `ssh` Stow packages. The helper needs Python 3, `nc`, and
the private webhook export from `davafons-infra/scripts/tower_power_webhooks.py`.
On macOS, put that export at
`~/Library/Application Support/tower-power/grok-actions.json`; on Linux, use
`${XDG_CONFIG_HOME:-~/.config}/tower-power/grok-actions.json`. Set its mode to
`600`. The helper uses only the `wake` URL and never prints it.

The ordinary aliases `tower`, `tower-lan`, and `tower-tailnet` never send a
wake request. Keep background tools such as Herdr on these passive aliases so
reconnects cannot wake an idle machine. SCP and SFTP wake Tower only when
explicitly using `tower-wake`. Inspecting settings with `ssh -G tower-wake`
does not wake it. Normal idle sleep remains enabled, and the wake hook does
not set a keep-awake hold.

```sh
python3 -B -m unittest -v bin/tests/test_tower_ssh_proxy.py
ssh tower-wake hostname
```

## Verify configuration behavior

Project-local [Yuke](.agents/skills/verify-yuke-profile/SKILL.md),
[Herdr](.agents/skills/verify-herdr-profile/SKILL.md), and
[Neovim](.agents/skills/verify-neovim-profile/SKILL.md) verification skills map
user-facing features to the existing isolated drivers. Follow their Doctor and
Drive instructions. Keep evidence after teardown and do not reload or automate
your active desktop session as part of a check. The
[davstack guide](agents/.agents/davstack/README.md) lists the reusable control
and verification-maintenance workflows.

## Formatting and linting

Neovim uses `,cf` for explicit formatting and `,cl` for standalone linting, with
language-server diagnostics while editing. Project-local tools take precedence;
Mason tools provide defaults when no local executable exists. Saving and fixing
remain explicit. The [tooling guide](TOOLING.md) lists coverage, repository
settings, native dependencies, verification commands, and app-specific formats
that intentionally have no generic formatter.
