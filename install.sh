#!/bin/bash

# Dotfiles installation script using GNU Stow
# Usage: ./install.sh [package1] [package2] ...

# Allow script to continue even if individual packages fail

DOTFILES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

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
    echo "       $0 [GPG-COMMAND] [ARGS...]"
    echo ""
    echo "Package Management Options:"
    echo "  -h, --help          Show this help message"
    echo "  -u, --uninstall     Uninstall packages instead of installing"
    echo ""
    echo "GPG Key Management Commands:"
    echo "  gpg-list            List all GPG keys in the system"
    echo "  gpg-export <key-id> Export GPG key by ID (securely encrypted)"
    echo "  gpg-list-available  List available GPG key files for import"
    echo "  gpg-import <file>   Import GPG key from file"
    echo ""
    echo "Available packages: $(find "$DOTFILES_DIR" -maxdepth 1 -type d ! -name '.*' ! -path "$DOTFILES_DIR" -printf '%f ' | sort)"
    echo ""
    echo "Package Examples:"
    echo "  $0 -h                 # Show help"
    echo "  $0 shell git tmux     # Install specific packages"
    echo "  $0 -u shell           # Uninstall shell package"
    echo ""
    echo "GPG Examples:"
    echo "  $0 gpg-list           # List all GPG keys"
    echo "  $0 gpg-export ABC123  # Export key with ID ABC123"
    echo "  $0 gpg-import key.asc # Import key from file"
}


# GPG key management functions
gpg_list_keys() {
    echo "Listing all GPG keys in the system:"
    echo ""
    echo "Public keys:"
    gpg --list-public-keys --keyid-format LONG 2>/dev/null || echo "No public keys found"
    echo ""
    echo "Private keys:"
    gpg --list-secret-keys --keyid-format LONG 2>/dev/null || echo "No private keys found"
}

gpg_export_key() {
    local key_id="$1"
    if [[ -z "$key_id" ]]; then
        echo "Error: Key ID is required"
        echo "Usage: $0 gpg-export <key-id>"
        echo "Use '$0 gpg-list' to see available keys"
        exit 1
    fi
    
    echo "Exporting GPG key $key_id (encrypted with passphrase)..."
    local output_file="gpg-key-${key_id}.asc"
    
    # Export public key
    if gpg --armor --export "$key_id" > "${output_file}.pub" 2>/dev/null; then
        echo "Public key exported to: ${output_file}.pub"
    else
        echo "Error: Failed to export public key for $key_id"
        rm -f "${output_file}.pub"
        exit 1
    fi
    
    # Export private key with encryption
    if gpg --armor --export-secret-keys "$key_id" | gpg --symmetric --cipher-algo AES256 --output "${output_file}.sec.gpg" 2>/dev/null; then
        echo "Private key exported (encrypted) to: ${output_file}.sec.gpg"
        echo "WARNING: Keep this file secure and remember the passphrase used for encryption!"
    else
        echo "Error: Failed to export private key for $key_id"
        rm -f "${output_file}.pub" "${output_file}.sec.gpg"
        exit 1
    fi
}

gpg_list_available() {
    echo "Listing available GPG key files for import:"
    echo ""
    
    local found_keys=false
    for file in *.asc *.gpg *.key *.pub; do
        if [[ -f "$file" ]]; then
            echo "  - $file"
            found_keys=true
        fi
    done
    
    if [[ "$found_keys" == false ]]; then
        echo "No GPG key files found in current directory"
        echo "Supported extensions: .asc, .gpg, .key, .pub"
    fi
}

gpg_import_key() {
    local key_file="$1"
    if [[ -z "$key_file" ]]; then
        echo "Error: Key file is required"
        echo "Usage: $0 gpg-import <key-file>"
        echo "Use '$0 gpg-list-available' to see available key files"
        exit 1
    fi
    
    if [[ ! -f "$key_file" ]]; then
        echo "Error: Key file '$key_file' not found"
        exit 1
    fi
    
    echo "Importing GPG key from: $key_file"
    
    # Check if file is encrypted (ends with .gpg and is not ASCII armored)
    if [[ "$key_file" == *.gpg ]] && ! head -1 "$key_file" | grep -q "BEGIN PGP"; then
        echo "Detected encrypted key file. Decrypting first..."
        local temp_file=$(mktemp)
        if gpg --decrypt "$key_file" > "$temp_file" 2>/dev/null; then
            gpg --import "$temp_file" && echo "Key imported successfully!"
            rm -f "$temp_file"
        else
            echo "Error: Failed to decrypt key file"
            rm -f "$temp_file"
            exit 1
        fi
    else
        gpg --import "$key_file" && echo "Key imported successfully!"
    fi
}

# Parse command line arguments
UNINSTALL=false
SHOW_HELP=false
SELECTED_PACKAGES=()
GPG_COMMAND=""
GPG_ARG=""

# Check for GPG commands first
if [[ $# -gt 0 ]]; then
    case $1 in
        gpg-list)
            GPG_COMMAND="list"
            shift
            ;;
        gpg-export)
            GPG_COMMAND="export"
            GPG_ARG="$2"
            shift 2
            ;;
        gpg-list-available)
            GPG_COMMAND="list-available"
            shift
            ;;
        gpg-import)
            GPG_COMMAND="import"
            GPG_ARG="$2"
            shift 2
            ;;
    esac
fi

# If GPG command was found, handle it
if [[ -n "$GPG_COMMAND" ]]; then
    case $GPG_COMMAND in
        list)
            gpg_list_keys
            exit 0
            ;;
        export)
            gpg_export_key "$GPG_ARG"
            exit 0
            ;;
        list-available)
            gpg_list_available
            exit 0
            ;;
        import)
            gpg_import_key "$GPG_ARG"
            exit 0
            ;;
    esac
fi

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