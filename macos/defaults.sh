#!/usr/bin/env bash
# macOS defaults configuration

set -euo pipefail

echo "Applying macOS defaults..."

# Show hidden files in Finder
defaults write com.apple.finder AppleShowAllFiles -bool true

# Disable .DS_Store on network drives
defaults write com.apple.desktopservices DSDontWriteNetworkStores -bool true

# Faster key repeat (crucial for coding)
defaults write NSGlobalDomain KeyRepeat -int 2
defaults write NSGlobalDomain InitialKeyRepeat -int 15

# Force ANSI (US) keyboard layout instead of JIS
defaults -currentHost write -g AppleKeyboardType -int 40

# Disable autocorrect in Terminal
defaults write com.apple.Terminal SpellCheckingEnabled -bool false

# Restart Finder to apply changes
killall Finder

echo "macOS defaults applied!"
