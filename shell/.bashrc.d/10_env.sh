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

# Configure Java version
export JAVA_HOME=`/usr/libexec/java_home -v 17`
export PATH=$PATH:$JAVA_HOME/bin

# Set rust cargo path
export PATH="$HOME/.cargo/bin:$PATH"

# Add zoxide
# (Fast enough that is not worth lazy loading)
eval "$(zoxide init bash)"

# Add pyenv
export PYENV_ROOT="$HOME/.pyenv"
[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"

# Add nvm 
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh" --no-use # This loads nvm
[ -s "$NVM_DIR/bash_completion" ] && . "$NVM_DIR/bash_completion"  # This loads nvm bash_completion

# Add uv installed packages to PATH
. "$HOME/.local/bin/env"
