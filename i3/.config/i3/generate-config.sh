#!/bin/bash
HOSTNAME=$(hostname)
CONFIG_DIR="$HOME/.config/i3"
OUTPUT_CONFIG="$CONFIG_DIR/config"
DEFAULT_CONFIG="$CONFIG_DIR/config.default"
HOST_CONFIG="$CONFIG_DIR/config.$HOSTNAME"

# Always start with base config
if [ -f "$DEFAULT_CONFIG" ]; then
    cp "$DEFAULT_CONFIG" "$OUTPUT_CONFIG"
else
    echo "Error: No default config found at $DEFAULT_CONFIG" >&2
    exit 1
fi

# Append hostname-specific config if it exists
if [ -f "$HOST_CONFIG" ]; then
    echo "# Host-specific config for $HOSTNAME" >> "$OUTPUT_CONFIG"
    cat "$HOST_CONFIG" >> "$OUTPUT_CONFIG"
fi

# Reload i3 if it's running
if pgrep -x i3 > /dev/null; then
    i3-msg restart
fi
