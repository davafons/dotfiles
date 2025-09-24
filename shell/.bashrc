#!/bin/bash

# If not running interactively, don't do anything
case $- in
	*i*) ;;
	  *) return;;
esac

__current_hostname=$(hostname -s)

if [[ $__bashrc_bench ]]; then
	__total_time=0
fi

for i in ~/.bashrc.d/*.sh; do
	if [[ "$(basename "$i")" =~ \.([^.]+)\.sh$ ]]; then
		__file_hostname=${BASH_REMATCH[1]}

		if [[ "$__file_hostname" != "$__current_hostname" ]]; then
			continue
		fi
	fi

	if [[ $__bashrc_bench ]]; then
        __time_file=$(mktemp)

        { time -p . "$i"; } 2> "$__time_file"

        elapsed_time=$(grep '^real' "$__time_file" | cut -d' ' -f2)
        rm "$__time_file"

        echo "$(basename "$i"): ${elapsed_time:-0}s"
        __total_time=$(echo "$__total_time + ${elapsed_time:-0}" | bc)
	else
		. "$i"
	fi
done

if [[ $__bashrc_bench ]]; then
    echo "-------------------------"
	echo "Total sourcing time: ${__total_time}s"
fi

unset i
unset __current_hostname
unset __file_hostname
unset __total_time
unset __time_file
unset elapsed_time

# Add RVM to PATH for scripting. Make sure this is the last PATH variable change.
export PATH="$PATH:$HOME/.rvm/bin"
