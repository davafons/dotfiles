#!/bin/bash

# Dotfiles installation script using GNU Stow
# Usage: ./install.sh [package1] [package2] ... or ./install.sh (for all packages)

set -e

DOTFILES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGES=(alacritty commitizen git i3 mpv nvim plex-mpv-shim ripgrep shell tmux vim alacritty-pc alacritty-laptop)

install_package() {
    local package=$1
    local hostname=$(hostname)
    local hostname_package="${package}-${hostname}"
    
    # Check if hostname-specific package exists
    if [[ -d "$DOTFILES_DIR/$hostname_package" ]]; then
        echo "Installing $hostname_package (hostname-specific for $hostname)..."
        stow -v -d "$DOTFILES_DIR" -t "$HOME" "$hostname_package"
    else
        echo "Installing $package..."
        stow -v -d "$DOTFILES_DIR" -t "$HOME" "$package"
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
    echo ""
    echo "Options:"
    echo "  -h, --help     Show this help message"
    echo "  -u, --uninstall Uninstall packages instead of installing"
    echo "  -l, --list     List available packages"
    echo ""
    echo "Available packages: ${PACKAGES[*]}"
    echo ""
    echo "Examples:"
    echo "  $0                    # Install all packages"
    echo "  $0 shell git tmux     # Install specific packages"
    echo "  $0 -u shell           # Uninstall shell package"
}

list_packages() {
    echo "Available packages:"
    for package in "${PACKAGES[@]}"; do
        echo "  - $package"
    done
}

# Parse command line arguments
UNINSTALL=false
SHOW_HELP=false
LIST_PACKAGES=false
SELECTED_PACKAGES=()

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
        -l|--list)
            LIST_PACKAGES=true
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

if [[ "$LIST_PACKAGES" == true ]]; then
    list_packages
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

# Use selected packages or all packages if none specified
if [[ ${#SELECTED_PACKAGES[@]} -eq 0 ]]; then
    SELECTED_PACKAGES=("${PACKAGES[@]}")
fi

# Validate selected packages
for package in "${SELECTED_PACKAGES[@]}"; do
    hostname=$(hostname)
    hostname_package="${package}-${hostname}"
    
    if [[ ! " ${PACKAGES[*]} " =~ " $package " ]]; then
        echo "Error: Unknown package '$package'"
        echo "Available packages: ${PACKAGES[*]}"
        exit 1
    fi
    
    # Check if hostname-specific package exists, otherwise check base package
    if [[ -d "$DOTFILES_DIR/$hostname_package" ]]; then
        continue  # hostname-specific package exists, validation passed
    elif [[ ! -d "$DOTFILES_DIR/$package" ]]; then
        echo "Error: Package directory '$package' and '$hostname_package' do not exist"
        exit 1
    fi
done

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