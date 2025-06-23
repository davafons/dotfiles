grbo() {
  git rebase --onto "$1" "$2^" "$2"
}

gbaco() {
  git branch -f "$1" && git checkout "$1"
}

gfr() {
  git reset @~ "$@" && git commit --amend --no-edit
}

killport() {
  lsof -n -i4TCP:$1 | awk '{print$2}' | tail -1 | xargs kill -9
}

b64() {
  echo -n "$1" | base64
}

db64() {
  echo -n "$1" | base64 --decode
}

wiped() {
  # stop and !! REMOVE !! all containers (looses all data inside containers)
  docker ps | awk '{print $1}' | grep -v CONTAINER | xargs docker stop && \
  docker ps -a | awk '{print $1}' | grep -v CONTAINER | xargs docker rm
}

# Usage: set_java <version> (e.g., set_java 17, set_java 11)
function set_java() {
  local version=$1
  if [ -z "$version" ]; then
    echo "Usage: set_java <version>"
    echo "Example: set_java 17"
    echo "Currently active: $(java -version 2>&1 | head -n 1 | cut -d\" -f 2)"
    echo "Available Java versions (via /usr/libexec/java_home -V):"
    /usr/libexec/java_home -V 2>&1
    return 1
  fi

  local java_home_path=$(/usr/libexec/java_home -v "$version" 2>/dev/null)

  if [ -z "$java_home_path" ]; then
    echo "Error: Java version '$version' not found by /usr/libexec/java_home."
    echo "Please ensure it's installed and discoverable, or adjust the path lookup."
    return 1
  fi

  export JAVA_HOME="$java_home_path"
  # Prepend JAVA_HOME/bin to PATH to ensure it's prioritized
  export PATH="$JAVA_HOME/bin:$(echo $PATH | sed "s#$JAVA_HOME/bin:##g" | sed "s#$(/usr/libexec/java_home -v [0-9.]* 2>/dev/null | sed -E 's/^\/.*\/bin//')##g")"
  # The sed command attempts to remove previous JAVA_HOME/bin entries to avoid duplication and keep PATH clean.
  # This specific sed might be overly complex or not perfectly robust for all PATH variations.
  # A simpler approach is to ensure JAVA_HOME/bin is always at the beginning.

  echo "Switched to Java $version:"
  echo "JAVA_HOME: $JAVA_HOME"
  java -version
}
