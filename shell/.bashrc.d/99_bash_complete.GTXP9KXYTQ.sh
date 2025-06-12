# Source the real bash_completion script first.
if [ -f /opt/homebrew/etc/profile.d/bash_completion.sh ]; then
    . /opt/homebrew/etc/profile.d/bash_completion.sh
fi

# Lazy Load bash complete in Mac
# complete() {
#     # Source the real bash_completion script first.
#     if [ -f /opt/homebrew/etc/profile.d/bash_completion.sh ]; then
#         . /opt/homebrew/etc/profile.d/bash_completion.sh
#     fi
#
#     # IMPORTANT: Manually unset this placeholder function.
#     # This is the key change that prevents the recursive crash.
#     unset -f complete
#
#     # Now, call the command again. Since our placeholder function is gone,
#     # this will safely call the *real* `complete` builtin that was just loaded.
#     complete "$@"
# }

