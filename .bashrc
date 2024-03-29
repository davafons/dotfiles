# Bashrc

# If not running interactively, don't do anything
[ -z "$PS1" ] && return

# Basic Shell configuration
. "$HOME/.shell-aliases"
. "$HOME/.shell-prompt"

# Disable ctrl-s (freeze console)
stty -ixon

# Specific settings for the local machine
[ -f ~/.extra ] && . ~/.extra

# Add fzf
[ -f ~/.fzf.bash ] && . ~/.fzf.bash

# Activate NVM
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh" --no-use # This loads nvm
[ -s "$NVM_DIR/bash_completion" ] && . "$NVM_DIR/bash_completion"  # This loads nvm bash_completion

export GPG_TTY=$(tty)
