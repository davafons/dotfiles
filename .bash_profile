. ~/.profile

# PERL_MM_OPT="INSTALL_BASE=$HOME/perl5" cpan local::lib
# eval "$(perl -I$HOME/perl5/lib/perl5 -Mlocal::lib)"

[ -f /opt/homebrew/etc/profile.d/bash_completion.sh ] && . /opt/homebrew/etc/profile.d/bash_completion.sh
[ -f /opt/homebrew/etc/profile.d/autojump.sh ] && . /opt/homebrew/etc/profile.d/autojump.sh

test -e "${HOME}/.iterm2_shell_integration.bash" && source "${HOME}/.iterm2_shell_integration.bash"

. ~/.bashrc
