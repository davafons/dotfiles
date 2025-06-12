# Cache the brew loading script to get faster loading times in bash
brew_executable=""

# Find the active brew executable
if [ -x "/opt/homebrew/bin/brew" ]; then
  brew_executable="/opt/homebrew/bin/brew"
elif [ -x "/usr/local/bin/brew" ]; then
  brew_executable="/usr/local/bin/brew"
fi

if [ -n "$brew_executable" ]; then
  brew_cache_path="${HOME}/Library/Caches/bash/brew-shellenv"

  # Regenerate the cache IF:
  # 1. The cache file doesn't exist (-f).
  # 2. OR the `brew` command is newer than (-nt) the cache file.
  if [ ! -f "$brew_cache_path" ] || [ "$brew_executable" -nt "$brew_cache_path" ]; then
    mkdir -p "$(dirname "$brew_cache_path")"
    "$brew_executable" shellenv > "$brew_cache_path"
  fi

  if [ -f "$brew_cache_path" ]; then
    . "$brew_cache_path"
  fi
fi

unset brew_executable brew_cache_path

# # This is the recommended way to initialize Homebrew for Bash
# # Use if the above settings fail for any reason
# if [ -x "/opt/homebrew/bin/brew" ]; then
#     # For Apple Silicon Macs
#     eval "$(/opt/homebrew/bin/brew shellenv)"
# elif [ -x "/usr/local/bin/brew" ]; then
#     # For Intel Macs
#     eval "$(/usr/local/bin/brew shellenv)"
# fi
