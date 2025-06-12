# If not running interactively, don't do anything
[ -z "$PS1" ] && return

# Basic Shell configuration
. "$HOME/.shell-aliases"
. "$HOME/.shell-prompt"

# Disable ctrl-s (freeze console)
stty -ixon

# Add fzf
[ -f ~/.fzf.bash ] && . ~/.fzf.bash

# Add zoxide
eval "$(zoxide init bash)"

# Add pyenv
export PYENV_ROOT="$HOME/.pyenv"
[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init - bash)"

# Add nvm 
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh" --no-use # This loads nvm
[ -s "$NVM_DIR/bash_completion" ] && . "$NVM_DIR/bash_completion"  # This loads nvm bash_completion

# --- Host-Specific Overrides
if [ -f "$HOME/.bashrc.$(hostname)" ]; then
    . "$HOME/.bashrc.$(hostname)"
fi
