# dotfiles

Personal configuration deployed with [GNU Stow](https://www.gnu.org/software/stow/).

## Installing

Each machine is declared by one explicit profile manifest in `profiles/`. A
profile is an allowlist: only its listed packages are linked into the home
directory. Package variants such as `git-work` are selected by the profile;
there is no hostname-based package replacement.

```sh
$ jj git clone https://github.com/davafons/dotfiles
$ cd dotfiles
$ make list-profiles
$ make plan PROFILE=mb
$ make install PROFILE=mb
```

`make` defaults `PROFILE` to the current hostname for compatibility. Specify
`PROFILE` explicitly on a new machine.

Useful commands:

```sh
make doctor PROFILE=mb
make status PROFILE=mb
make install PROFILE=work
make install PACKAGES="shell git jj" PROFILE=mb
```
