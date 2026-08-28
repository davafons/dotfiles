[[ -f ~/.bashrc ]] && . ~/.bashrc

if command -v mise >/dev/null 2>&1; then
  eval "$(mise activate bash)"
fi

[[ -f "$HOME/.local/bin/env" ]] && . "$HOME/.local/bin/env"

# Hermes Agent — ensure ~/.local/bin is on PATH
export PATH="$HOME/.local/bin:$PATH"

# Added by LM Studio CLI (lms)
export PATH="$PATH:/Users/davafons/.lmstudio/bin"
# End of LM Studio CLI section

# Added by OrbStack: command-line tools and integration
# This won't be added again if you remove it.
source ~/.orbstack/shell/init.bash 2>/dev/null || :

[[ -r ~/.bashrc ]] && source ~/.bashrc
. "$HOME/.cargo/env"
