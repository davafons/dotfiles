[[ -f ~/.bashrc ]] && . ~/.bashrc

[[ -f "$HOME/.local/bin/env" ]] && . "$HOME/.local/bin/env"

# Hermes Agent — ensure ~/.local/bin is on PATH
export PATH="$HOME/.local/bin:$PATH"

# Added by LM Studio CLI (lms)
export PATH="$PATH:/Users/davafons/.lmstudio/bin"
# End of LM Studio CLI section
