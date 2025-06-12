#!sh
if [ -f /opt/homebrew/etc/profile.d/bash_completion.sh ]; then
    . /opt/homebrew/etc/profile.d/bash_completion.sh
fi

# JetBrains Toolbox App
export PATH="$PATH:~/.local/share/JetBrains/Toolbox/scripts"

# Configure Java version
export JAVA_HOME=`/usr/libexec/java_home -v 17`
export PATH=$PATH:$JAVA_HOME/bin

export TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock
export DOCKER_HOST="unix://${HOME}/.colima/default/docker.sock"
# TODO: Confirm this is not required
# export TESTCONTAINERS_HOST_OVERRIDE=$(colima ls -j | jq -r '.address')
