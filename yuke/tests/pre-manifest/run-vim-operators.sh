#!/bin/bash
# Run profile key tests without a terminal, credentials, or the user's session store.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
tmp=$(mktemp -d /tmp/yuke-vim-check.XXXXXX)
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/yuke"
printf 'import %s;\n' "\"$here/vim-operators.js\"" "\"$here/vim-extended.js\"" "\"$here/vim-parity.js\"" > "$tmp/yuke/index.js"
XDG_CONFIG_HOME="$tmp" XDG_DATA_HOME="$tmp/data" XDG_STATE_HOME="$tmp/state" YUKE_APPNAME=yuke yuke check
