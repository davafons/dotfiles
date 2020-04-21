# Profile

# set PATH so it includes user's private bin if it exists
export PATH="$HOME/bin:$PATH"

# set PATH for Poetry binary
export PATH="$HOME/.poetry/bin:$PATH"

# Add NVM if installed
export NVM_DIR="$HOME/.nvm"

function _install_nvm() {
  unset -f nvm npm node
  # Set up "nvm" could use "--no-use" to defer setup, but we are here to use it
  [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh" # This sets up nvm
  [ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"  # nvm bash_completion
  "$@"
}

_install_nvm nvm "$@"
_install_nvm npm "$@"
_install_nvm node "$@"

# Add pyenv
eval "$(pyenv init -)"

# Vim as default editor
export VISUAL=vim
export EDITOR="$VISUAL"

# ripgrep config file path
export RIPGREP_CONFIG_PATH="$HOME/.ripgreprc"

# Configure FZF
export FZF_DEFAULT_COMMAND='rg --files'

_gen_fzf_default_opts() {
  local base03="234"
  local base02="235"
  local base01="240"
  local base00="241"
  local base0="244"
  local base1="245"
  local base2="254"
  local base3="230"
  local yellow="136"
  local orange="166"
  local red="160"
  local magenta="125"
  local violet="61"
  local blue="33"
  local cyan="37"
  local green="64"

  # Comment and uncomment below for the light theme.

  # Solarized Dark color scheme for fzf
  export FZF_DEFAULT_OPTS="
    --color fg:-1,bg:-1,hl:$blue,fg+:$base2,bg+:$base02,hl+:$blue
    --color info:$yellow,prompt:$yellow,pointer:$base3,marker:$base3,spinner:$yellow
  "
}
_gen_fzf_default_opts

export PATH="$HOME/.cargo/bin:$PATH"
