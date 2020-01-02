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
