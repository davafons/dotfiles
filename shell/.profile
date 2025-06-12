# Theme
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

# Exports

if [ -f "/opt/homebrew/bin/brew" ]; then
  eval "$(/opt/homebrew/bin/brew shellenv)"
fi

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

# Configure FZF
export FZF_DEFAULT_COMMAND='rg --files'

# Configure Java version
export JAVA_HOME=`/usr/libexec/java_home -v 17`
export PATH=$PATH:$JAVA_HOME/bin

# Set rust cargo path
export PATH="$HOME/.cargo/bin:$PATH"

# Add uv installed packages to PATH
. "$HOME/.local/bin/env"

# --- Host-Specific Overrides
if [ -f "$HOME/.profile.$(hostname)" ]; then
    . "$HOME/.profile.$(hostname)"
fi
