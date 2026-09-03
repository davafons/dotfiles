[[ -f ~/.bashrc ]] && . ~/.bashrc

if command -v mise >/dev/null 2>&1; then
  eval "$(mise activate bash)"
fi

[[ -f "$HOME/.local/bin/env" ]] && . "$HOME/.local/bin/env"

export PATH="$HOME/.local/bin:$PATH"

wariwari_nofile_limit="$(ulimit -n 2>/dev/null || printf 0)"
if [ "$wariwari_nofile_limit" -lt 65536 ] 2>/dev/null; then
  ulimit -n 65536 2>/dev/null || :
fi
unset wariwari_nofile_limit

# Added by LM Studio CLI (lms)
export PATH="$PATH:/Users/davafons/.lmstudio/bin"
# End of LM Studio CLI section

# Added by OrbStack: command-line tools and integration
# This won't be added again if you remove it.
source ~/.orbstack/shell/init.bash 2>/dev/null || :

[[ -r ~/.bashrc ]] && source ~/.bashrc
. "$HOME/.cargo/env"
