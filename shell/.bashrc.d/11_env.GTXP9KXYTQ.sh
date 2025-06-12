#!sh

# JetBrains Toolbox App
export PATH="$PATH:~/.local/share/JetBrains/Toolbox/scripts"

export TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock
export DOCKER_HOST="unix://${HOME}/.colima/default/docker.sock"
# TODO: Confirm this is not required
# export TESTCONTAINERS_HOST_OVERRIDE=$(colima ls -j | jq -r '.address')
