# Bashrc

# If not running interactively, don't do anything
[ -z "$PS1" ] && return

# Basic Shell configuration
. "$HOME/.shell-aliases"
. "$HOME/.prompt"

# Disable ctrl-s (freeze console)
stty -ixon

# Auto-cd directories
shopt -s autocd

# Add fzf
[ -f ~/.fzf.bash ] && . ~/.fzf.bash

# Settings exclusive for the local machine
[ -f ~/.extra ] && . ~/.extra


# Run a tmux session if tmux is installed
if command -v tmux &> /dev/null && [ -n "$PS1" ] && [[ ! "$TERM" =~ screen ]] && [[ ! "$TERM" =~ tmux ]] && [ -z "$TMUX" ]; then
  exec tmux
fi

export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"  # This loads nvm
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"  # This loads nvm bash_completion
