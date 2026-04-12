# Set PATH so it includes user's private bin
export PATH="$HOME/bin:$PATH"

# Set nvim as default editor
export VISUAL=nvim
export EDITOR="$VISUAL"

# Set TTY as the method for GPG signing
export GPG_TTY=$(tty)

# Set PATH for Poetry binary
export PATH="$HOME/.poetry/bin:$PATH"

# Activate mise (version manager for node, python, ruby, etc.)
eval "$(mise activate bash)"

# ripgrep config file path
export RIPGREP_CONFIG_PATH="$HOME/.ripgreprc"

# Set rust cargo path
export PATH="$HOME/.cargo/bin:$PATH"

# Lazy-load zoxide (--cmd cd enables fuzzy matching via cd, e.g. "cd dot")
cd() {
  unset -f cd
  eval "$(zoxide init bash --cmd cd)"
  cd "$@"
}

# bash-completion (homebrew)
[[ -r "/opt/homebrew/etc/profile.d/bash_completion.sh" ]] && . "/opt/homebrew/etc/profile.d/bash_completion.sh"

# fzf shell integration (Ctrl+R history, Ctrl+T file search)
eval "$(fzf --bash)"

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

# Export PATH for lmstudio
export PATH="$PATH:~/.lmstudio/bin"

export PATH="$PATH:/opt/jai/bin"
export PATH="$PATH:/opt/Jails/bin"
