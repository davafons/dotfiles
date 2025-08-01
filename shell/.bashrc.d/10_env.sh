# Set PATH so it includes user's private bin
export PATH="$HOME/bin:$PATH"

# Set nvim as default editor
export VISUAL=nvim
export EDITOR="$VISUAL"

# Set TTY as the method for GPG signing
export GPG_TTY=$(tty)

# Set PATH for Poetry binary
export PATH="$HOME/.poetry/bin:$PATH"

# Add NVM if installed
export NVM_DIR="$HOME/.nvm"

# ripgrep config file path
export RIPGREP_CONFIG_PATH="$HOME/.ripgreprc"

# Set rust cargo path
export PATH="$HOME/.cargo/bin:$PATH"

# Lazy-load zoxide
z() {
  unset -f z
  eval "$(zoxide init bash)"
  z "$@"
}

# Lazy-load pyenv
pyenv() {
  unset -f pyenv
  eval "$(pyenv init - bash)"
  pyenv "$@"
}

# Add pyenv
export PYENV_ROOT="$HOME/.pyenv"
[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"

# Add nvm 
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh" --no-use # This loads nvm
[ -s "$NVM_DIR/bash_completion" ] && . "$NVM_DIR/bash_completion"  # This loads nvm bash_completion

# Add rvm
[[ -s "$HOME/.rvm/scripts/rvm" ]] && source "$HOME/.rvm/scripts/rvm" # Load RVM into a shell session *as a function*
export PATH="$PATH:$HOME/.rvm/bin"

# Add uv installed packages to PATH
. "$HOME/.local/bin/env"

# bun
export BUN_INSTALL="$HOME/.bun"
export PATH="$BUN_INSTALL/bin:$PATH"

# Source local sensitive environment variables (not committed to git)
[ -f "$HOME/.bashrc.d/10_env.local.sh" ] && source "$HOME/.bashrc.d/10_env.local.sh"

# setup git autocompletion
if [ -f "/usr/share/bash-completion/completions/git" ]; then
  source /usr/share/bash-completion/completions/git
  __git_complete g __git_main # Enable git completion for 'g' alias
fi
