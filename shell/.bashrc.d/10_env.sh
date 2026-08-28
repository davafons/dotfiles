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

# Ansible on macOS. Without this, any play that resolves a secret dies partway
# with "A worker was found in a dead state" and never prints a recap, so it
# reads as a hung play rather than an error. Ansible forks a worker per host,
# and boto3 -- which the amazon.aws.ssm_parameter lookup uses -- makes
# Objective-C runtime calls that abort in a forked child on macOS 10.13+.
#
# It has to be in the environment: libobjc reads this at load time, so there is
# no ansible.cfg equivalent and setting it from inside Python is already too
# late. Guarded by OSTYPE rather than hostname because it is a macOS fact, not
# a machine fact, and this file is shared with the Linux boxes.
if [[ "$OSTYPE" == darwin* ]]; then
  export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES
fi

# Let Node trust rb-portless's local CA, so a Node process can reach another app
# served at https://<name>.localhost.
#
# rb-portless mints its own CA (~/.rb-portless/ca.pem) and installs it in the
# login keychain, which is why browsers and Ruby accept those hosts. Node does
# not read the keychain -- it compiles in its own root store -- so a fetch to a
# portless host dies with SELF_SIGNED_CERT_IN_CHAIN. This is the only way to tell
# it otherwise: Node reads the variable at startup, before any dotenv the app
# loads, so it cannot live in a project's .env.
#
# Guarded on the CA existing rather than on the hostname, because it is an
# "rb-portless is installed here" fact rather than a machine fact, and this file
# is shared with the Linux boxes. Never set on a server: production serves real
# certificates that Node already trusts, this CA only signs .localhost names, and
# its key can mint a trusted cert for any host.
if [ -f "$HOME/.rb-portless/ca.pem" ]; then
  export NODE_EXTRA_CA_CERTS="$HOME/.rb-portless/ca.pem"
fi
