#!bash

# If not running interactively, don't do anything
case $- in
  *i*) ;;
  *) return;;
esac

__current_hostname=$(hostname -s)

for i in ~/.bashrc.d/*.sh; do
  # Check if a file is host-specific (e.g., "name.some-host.sh")
  # The regex checks for a pattern of ".[something]." before the "sh" extension.
  if [[ "$(basename "$i")" =~ \.([^.]+)\.sh$ ]]; then
    # Get the hostname part from the filename
    __file_hostname=${BASH_REMATCH[1]}

    if [[ "$__file_hostname" != "$__current_hostname" ]]; then
      continue
    fi
  fi

  if [[ $__bashrc_bench ]]; then
    TIMEFORMAT="$i: %R"
    time . "$i"
    unset TIMEFORMAT
  else
    . "$i"
  fi
done; unset i
