#!/bin/bash

# Dotfiles installation script using GNU Stow
# Usage: ./install.sh [package1] [package2] ...
# Usage: ./install.sh "key" (to install predefined package lists)

# Allow script to continue even if individual packages fail

DOTFILES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Define predefined package lists
declare -A PACKAGE_LISTS
PACKAGE_LISTS["omen"]="bin shell git i3 tmux nvim alacritty ssh x11 fcitx"

install_package() {
    local package=$1
    local hostname=$(hostname)
    local hostname_package="${package}-${hostname}"
    
    # Try hostname-specific package first, then fall back to base package
    if [[ -d "$DOTFILES_DIR/$hostname_package" ]]; then
        echo "Installing $hostname_package (hostname-specific for $hostname)..."
        stow -v -d "$DOTFILES_DIR" -t "$HOME" "$hostname_package" || echo "Failed to install $hostname_package"
    elif [[ -d "$DOTFILES_DIR/$package" ]]; then
        echo "Installing $package..."
        stow -v -d "$DOTFILES_DIR" -t "$HOME" "$package" || echo "Failed to install $package"
    else
        echo "Package '$package' not found (tried both '$package' and '$hostname_package')"
    fi
}

uninstall_package() {
    local package=$1
    local hostname=$(hostname)
    local hostname_package="${package}-${hostname}"
    
    # Check if hostname-specific package exists and is stowed
    if [[ -d "$DOTFILES_DIR/$hostname_package" ]]; then
        echo "Uninstalling $hostname_package (hostname-specific for $hostname)..."
        stow -v -d "$DOTFILES_DIR" -t "$HOME" -D "$hostname_package" 2>/dev/null || true
    fi
    
    # Also try to uninstall the base package in case it was stowed
    echo "Uninstalling $package..."
    stow -v -d "$DOTFILES_DIR" -t "$HOME" -D "$package" 2>/dev/null || true
}

show_help() {
    echo "Usage: $0 [OPTIONS] [PACKAGES...]"
    echo "Usage: $0 [OPTIONS] \"KEY\""
    echo ""
    echo "Options:"
    echo "  -h, --help          Show this help message"
    echo "  -u, --uninstall     Uninstall packages instead of installing"
    echo ""
    echo "Available packages: $(find "$DOTFILES_DIR" -maxdepth 1 -type d ! -name '.*' ! -path "$DOTFILES_DIR" -printf '%f ' | sort)"
    echo ""
    echo "Available package lists:"
    for key in "${!PACKAGE_LISTS[@]}"; do
        echo "  $key: ${PACKAGE_LISTS[$key]}"
    done
    echo ""
    echo "Examples:"
    echo "  $0 -h                 # Show help"
    echo "  $0 shell git tmux     # Install specific packages"
    echo "  $0 \"omen\"             # Install omen package list"
    echo "  $0 -u shell           # Uninstall shell package"
    echo "  $0 -u \"omen\"          # Uninstall omen package list"
}


# Parse command line arguments
UNINSTALL=false
SHOW_HELP=false
SELECTED_PACKAGES=()

# Parse regular options
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            SHOW_HELP=true
            shift
            ;;
        -u|--uninstall)
            UNINSTALL=true
            shift
            ;;
        -*)
            echo "Unknown option $1"
            exit 1
            ;;
        *)
            SELECTED_PACKAGES+=("$1")
            shift
            ;;
    esac
done

if [[ "$SHOW_HELP" == true ]]; then
    show_help
    exit 0
fi


# Check if stow is installed
if ! command -v stow &> /dev/null; then
    echo "Error: GNU Stow is not installed."
    echo "Please install it using your package manager:"
    echo "  Ubuntu/Debian: sudo apt install stow"
    echo "  Arch Linux: sudo pacman -S stow"
    echo "  macOS: brew install stow"
    exit 1
fi

# Show help if no packages specified
if [[ ${#SELECTED_PACKAGES[@]} -eq 0 ]]; then
    show_help
    exit 0
fi

# Check if the single argument is a predefined package list
if [[ ${#SELECTED_PACKAGES[@]} -eq 1 ]] && [[ -n "${PACKAGE_LISTS[${SELECTED_PACKAGES[0]}]}" ]]; then
    PACKAGE_LIST_KEY="${SELECTED_PACKAGES[0]}"
    read -ra SELECTED_PACKAGES <<< "${PACKAGE_LISTS[$PACKAGE_LIST_KEY]}"
    echo "Using package list '$PACKAGE_LIST_KEY': ${SELECTED_PACKAGES[*]}"
fi

# Let stow handle package validation - it will show appropriate errors

# Install or uninstall packages
cd "$DOTFILES_DIR"

if [[ "$UNINSTALL" == true ]]; then
    echo "Uninstalling packages: ${SELECTED_PACKAGES[*]}"
    for package in "${SELECTED_PACKAGES[@]}"; do
        uninstall_package "$package"
    done
else
    echo "Installing packages: ${SELECTED_PACKAGES[*]}"
    for package in "${SELECTED_PACKAGES[@]}"; do
        install_package "$package"
    done
fi

echo "Done!"
