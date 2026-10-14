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

`make` defaults `PROFILE` to the current hostname for compatibility. Specify
`PROFILE` explicitly on a new machine.

Useful commands:

```sh
make doctor PROFILE=mb
make status PROFILE=mb
make install PROFILE=work
make install PACKAGES="shell git jj" PROFILE=mb
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
