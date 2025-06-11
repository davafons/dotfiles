# dotfiles
Personal __dotfiles__ for Linux systems with Arch.

## Installing

This dotfiles repository uses [GNU Stow](https://www.gnu.org/software/stow/):

```sh
$ git clone https://github.com/davafons/dotfiles
$ cd dotfiles
$ ./install.sh <package>  # e.g., stow git bash mpv
```

### Hostname resolution

You can suffix a package with `-$(hostname)`, and it will be preferred over the global package if
installing in a device with the same hostname.

## GPG

The install script includes GPG key management functionality for securely handling GPG keys across different systems.

### Available Commands
```sh
# List all GPG keys in the system
./install.sh gpg-list
# Export a GPG key by ID (both public and private keys)
./install.sh gpg-export <key-id>
# List available key files for import
./install.sh gpg-list-available
# Import a GPG key from file
./install.sh gpg-import <key-file>
```

**Security Note**: Private keys are exported with double encryption:
1. Standard GPG armor format
2. Additional AES256 symmetric encryption with passphrase
