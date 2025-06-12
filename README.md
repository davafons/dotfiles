# dotfiles
Personal __dotfiles__ for Linux systems with Arch.

## Installing

This dotfiles repository uses [GNU Stow](https://www.gnu.org/software/stow/):

```sh
$ git clone https://github.com/davafons/dotfiles
$ cd dotfiles
$ make install <package>  # e.g., stow git bash nvim
```

### Hostname resolution

You can suffix a package with `-$(hostname)`, and it will be preferred over the global package if
installing in a device with the same hostname.
