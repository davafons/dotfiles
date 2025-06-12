#!/usr/bin/make -f
# Dotfiles installation using GNU Stow Usage: make install [PACKAGES="package1 package2 ..."]
# Usage: make uninstall [PACKAGES="package1 package2 ..."]

DOTFILES_DIR := $(shell pwd)
HOSTNAME := $(shell hostname)
STOW := stow

# Predefined package lists by hostname
ifeq ($(HOSTNAME),omen)
	DEFAULT_PACKAGES := bin shell git i3 tmux nvim alacritty ssh x11 fcitx5
else
	DEFAULT_PACKAGES := bin shell git i3 tmux nvim
endif

# Use provided packages or default for hostname
PACKAGES ?= $(DEFAULT_PACKAGES)

# Helper function to check if a directory exists
define check_package
	$(if $(wildcard $(DOTFILES_DIR)/$(1)-$(HOSTNAME)), \
		$(1)-$(HOSTNAME), \
		$(if $(wildcard $(DOTFILES_DIR)/$(1)), \
			$(1), \
			$(error Package '$(1)' not found (tried both '$(1)' and '$(1)-$(HOSTNAME)')))
endef

.PHONY: help install uninstall list check-stow

# Default target
all: help

help:
	@echo "Usage: make [TARGET] [PACKAGES=\"package1 package2 ...\"]"
	@echo ""
	@echo "Targets:"
	@echo "  install     Install packages (default: hostname-specific packages)"
	@echo "  uninstall   Uninstall packages"
	@echo "  list        List available packages"
	@echo "  help        Show this help message"
	@echo ""
	@echo "Current hostname: $(HOSTNAME)"
	@echo "Default packages for $(HOSTNAME): $(DEFAULT_PACKAGES)"
	@echo ""
	@echo "Examples:"
	@echo "  make install                    # Install default packages for hostname"
	@echo "  make install PACKAGES=\"shell git\"  # Install specific packages"
	@echo "  make uninstall PACKAGES=\"shell\"    # Uninstall specific package"

install: check-stow
	@echo "Installing packages for hostname '$(HOSTNAME)': $(PACKAGES)"
	@for package in $(PACKAGES); do \
		hostname_package="$$package-$(HOSTNAME)"; \
		if [ -d "$(DOTFILES_DIR)/$$hostname_package" ]; then \
			echo "Installing $$hostname_package (hostname-specific for $(HOSTNAME))..."; \
			$(STOW) -v -d "$(DOTFILES_DIR)" -t "$(HOME)" "$$hostname_package" || echo "Failed to install $$hostname_package"; \
		elif [ -d "$(DOTFILES_DIR)/$$package" ]; then \
			echo "Installing $$package..."; \
			$(STOW) -v -d "$(DOTFILES_DIR)" -t "$(HOME)" "$$package" || echo "Failed to install $$package"; \
		else \
			echo "Package '$$package' not found (tried both '$$package' and '$$hostname_package')"; \
		fi; \
	done
	@echo "Installation complete!"

uninstall: check-stow
	@echo "Uninstalling packages: $(PACKAGES)"
	@for package in $(PACKAGES); do \
		hostname_package="$$package-$(HOSTNAME)"; \
		if [ -d "$(DOTFILES_DIR)/$$hostname_package" ]; then \
			echo "Uninstalling $$hostname_package (hostname-specific for $(HOSTNAME))..."; \
			$(STOW) -v -d "$(DOTFILES_DIR)" -t "$(HOME)" -D "$$hostname_package" 2>/dev/null || true; \
		fi; \
		echo "Uninstalling $$package..."; \
		$(STOW) -v -d "$(DOTFILES_DIR)" -t "$(HOME)" -D "$$package" 2>/dev/null || true; \
	done
	@echo "Uninstallation complete!"

list:
	@echo "Available packages:"
	@find "$(DOTFILES_DIR)" -maxdepth 1 -type d ! -name '.*' ! -path "$(DOTFILES_DIR)" -printf '%f\n' | sort

check-stow:
	@command -v $(STOW) >/dev/null 2>&1 || { \
		echo "Error: GNU Stow is not installed."; \
		echo "Please install it using your package manager:"; \
		echo "  Ubuntu/Debian: sudo apt install stow"; \
		echo "  Arch Linux: sudo pacman -S stow"; \
		echo "  macOS: brew install stow"; \
		exit 1; \
	}
