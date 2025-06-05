# Bashrc

# If not running interactively, don't do anything
[ -z "$PS1" ] && return

# Basic Shell configuration
. "$HOME/.shell-aliases"
. "$HOME/.shell-prompt"

# Add zoxide
eval "$(zoxide init bash)"

# Disable ctrl-s (freeze console)
stty -ixon

# Specific settings for the local machine
[ -f ~/.extra ] && . ~/.extra

# Add fzf
[ -f ~/.fzf.bash ] && . ~/.fzf.bash

export GPG_TTY=$(tty)

start_colima() {
  local CERTS="${HOME}/.ca-certificates"
  local URL="registry-1.docker.io:443"
  mkdir -p ${CERTS}
  cp -f '/Library/Application Support/Netskope/STAgent/download/nscacert_combined.pem' ${CERTS}
  openssl s_client -showcerts -connect ${URL} </dev/null 2>/dev/null|openssl x509 -outform PEM >${CERTS}/docker-com.pem
  openssl s_client -showcerts -verify 5 -connect ${URL} </dev/null 2>/dev/null | sed -ne '/-BEGIN/,/-END/p' >${CERTS}/docker-com-chain.pem
  # colima start --memory 8 --cpu 2 --vm-type=vz --mount-type=virtiofs --network-address --vz-rosetta
  colima start -t qemu --cpu 2 --memory 8 --disk 80 --mount-type=virtiofs --network-address --edit

  colima ssh -- sudo cp ${CERTS}/* /usr/local/share/ca-certificates/
  colima ssh -- sudo update-ca-certificates
  colima ssh -- sudo service docker restart
}

export TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock
export TESTCONTAINERS_HOST_OVERRIDE=$(colima ls -j | jq -r '.address')
export DOCKER_HOST="unix://${HOME}/.colima/default/docker.sock"

. "$HOME/.local/bin/env"
