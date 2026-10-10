# dotfiles

Personal configuration deployed with [GNU Stow](https://www.gnu.org/software/stow/).

## Installing

Each machine is declared by one explicit profile manifest in `profiles/`. A
profile is an allowlist: only its listed packages are linked into the home
directory. Package variants such as `git-work` are selected by the profile;
there is no hostname-based package replacement.

```sh
$ git clone --recurse-submodules https://github.com/davafons/dotfiles
$ cd dotfiles
$ jj git init --colocate
$ make list-profiles
$ make plan PROFILE=mb
$ make install PROFILE=mb
```

The initial Git clone initializes the pinned Neovim submodule. After
initializing the colocated repository, use `jj` for version-control operations.

`make` defaults `PROFILE` to the current hostname for compatibility. Specify
`PROFILE` explicitly on a new machine.

Obsidian configuration and vaults are managed by Syncthing, not by these packages.

Useful commands:

```sh
make doctor PROFILE=mb
make status PROFILE=mb
make install PROFILE=work
make install PACKAGES="shell git jj" PROFILE=mb
```
