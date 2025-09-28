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

gpr() {
  # Default remote is 'origin', but can be overridden by passing an argument (e.g., gpr upstream)
  local remote="${1:-origin}"
  local branch
  branch=$(git rev-parse --abbrev-ref HEAD)

  if ! git config "branch.${branch}.remote" >/dev/null 2>&1; then
    echo "-! No tracking information for branch '${branch}'. Setting upstream to '${remote}/${branch}'."
    git branch --set-upstream-to="${remote}/${branch}" "${branch}"
  fi

  git pull --rebase
}

# Usage: set_java <version> (e.g., set_java 17, set_java 11)
set_java() {
  local version=$1
  if [ -z "$version" ]; then
    echo "Usage: set_java <version>"
    echo "Example: set_java 17"
    echo "Currently active: $(java -version 2>&1 | head -n 1 | cut -d\" -f 2)"
    echo "Available Java versions (via /usr/libexec/java_home -V):"
    /usr/libexec/java_home -V 2>&1 | grep -E 'Java [0-9]+\.[0-9]+\.[0-9]+' | sed 's/.*Java \([0-9\.]\+\).*/- \1/'
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

#!/bin/bash
function caffeine() {
  status=`xset -q | grep 'DPMS is' | awk '{ print $3 }'`
  if [ $status == 'Enabled' ]; then
    xset -dpms && \
      dunstify 'Screen suspend is disabled.'
  else
    xset +dpms && \
      dunstify 'Screen suspend is enabled.'
  fi
}

function set_2k() {
  local display=${1:-DP-4}
  local best_rate=$(_get_best_rate "$display" "2560x1440")
  xrandr --output "$display" --mode 2560x1440 --rate "$best_rate"
}

function set_4k() {
  local display=${1:-DP-4}
  local best_rate=$(_get_best_rate "$display" "3840x2160")
  xrandr --output "$display" --mode 3840x2160 --rate "$best_rate"
}

function set_1080() {
  local display=${1:-DP-4}
  local best_rate=$(_get_best_rate "$display" "1920x1080")
  xrandr --output "$display" --mode 1920x1080 --rate "$best_rate"
}

_get_best_rate() {
  local display=$1
  local resolution=$2
  local line=$(xrandr | grep -A 50 "^$display connected" | grep "$resolution" | head -1)
  if [ -n "$line" ]; then
    echo "$line" | awk '{
      max_rate = 0
      for (i = 2; i <= NF; i++) {
        rate = $i
        gsub(/[*+]/, "", rate)
        if (rate ~ /^[0-9]+\.?[0-9]*$/ && rate > max_rate) {
          max_rate = rate
        }
      }
      if (max_rate > 0) {
        print max_rate
      }
    }'
  fi
}

_display_completion() {
  local cur=${COMP_WORDS[COMP_CWORD]}
  local displays=$(xrandr --listmonitors | grep -o '[A-Z][A-Z]-[0-9]*' | sort -u)
  COMPREPLY=($(compgen -W "$displays" -- "$cur"))
}
complete -F _display_completion set_2k
complete -F _display_completion set_4k
complete -F _display_completion set_1080
