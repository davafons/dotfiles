#!/usr/bin/make -f

DOTFILES_DIR := $(shell pwd)
HOSTNAME := $(shell hostname)
STOW := stow
PACKAGE_DIR := packages

# Predefined package lists by hostname
ifeq ($(HOSTNAME),omen)
	DEFAULT_PACKAGES := bin shell git i3 tmux nvim alacritty ssh x11 fcitx5 obsidian mimeapps
else ifeq ($(HOSTNAME),tower)
	DEFAULT_PACKAGES := bin shell git i3 tmux nvim alacritty ssh x11 fcitx5 obsidian mimeapps
else ifeq ($(HOSTNAME),GTXP9KXYTQ)
	DEFAULT_PACKAGES := bin shell git aerospace tmux nvim alacritty ssh obsidian
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

.PHONY: help install uninstall list check-stow install-packages install-packages-non-aur install-packages-aur list-installed

# Default target
all: help

# Default goal
.DEFAULT_GOAL := help

help:
	@printf "\e[34mDotfiles Management with GNU Stow and Package Installation\e[0m\n"
	@echo "Usage: make [TARGET] [PACKAGES=\"package1 package2 ...\"]"
	@echo ""
	@printf "\e[33mDotfiles Targets:\e[0m\n"
	@printf "  \e[32minstall\e[0m             Install dotfiles (default: hostname-specific packages)\n"
	@printf "  \e[32muninstall\e[0m           Uninstall dotfiles\n"
	@printf "  \e[32mlist\e[0m                List available dotfiles packages\n"
	@echo ""
	@printf "\e[33mSystem Package Targets:\e[0m\n"
	@printf "  \e[32minstall-packages\e[0m    Install default and host-specific packages\n"
	@printf "  \e[32minstall-packages-non-aur\e[0m Install only non-AUR packages\n"
	@printf "  \e[32minstall-packages-aur\e[0m Install only AUR packages\n"
	@printf "  \e[32mlist-installed\e[0m      List currently installed packages\n"
	@printf "  \e[32mshow-config\e[0m         Show current configuration\n"
	@printf "  \e[32mhelp\e[0m                Show this help message\n"
	@echo ""
	@echo "Current hostname: $(HOSTNAME)"
	@echo "Default dotfiles for $(HOSTNAME): $(DEFAULT_PACKAGES)"

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

# Package management targets
install-packages: install-packages-non-aur install-packages-aur
	@printf "\e[32mAll package installation complete!\e[0m\n"

# Install only non-AUR packages
install-packages-non-aur:
	@printf "\e[34mInstalling non-AUR packages for host: $(HOSTNAME)\e[0m\n"
	@echo "=================================="
	@printf "\e[33mInstalling default packages...\e[0m\n"
	@if [ -f "$(PACKAGE_DIR)/default.txt" ] && [ -s "$(PACKAGE_DIR)/default.txt" ]; then \
		sudo pacman -S --needed $$(cat $(PACKAGE_DIR)/default.txt); \
	else \
		printf "\e[31mNo default packages found\e[0m\n"; \
	fi
	@printf "\e[33mInstalling host-specific packages...\e[0m\n"
	@if [ -f "$(PACKAGE_DIR)/$(HOSTNAME).txt" ] && [ -s "$(PACKAGE_DIR)/$(HOSTNAME).txt" ]; then \
		sudo pacman -S --needed $$(cat $(PACKAGE_DIR)/$(HOSTNAME).txt); \
	else \
		printf "\e[33mNo host-specific packages found for $(HOSTNAME)\e[0m\n"; \
	fi
	@printf "\e[32mNon-AUR package installation complete!\e[0m\n"

# Install only AUR packages
install-packages-aur:
	@printf "\e[34mInstalling AUR packages for host: $(HOSTNAME)\e[0m\n"
	@echo "=================================="
	@printf "\e[33mInstalling default AUR packages...\e[0m\n"
	@if [ -f "$(PACKAGE_DIR)/default-aur.txt" ] && [ -s "$(PACKAGE_DIR)/default-aur.txt" ]; then \
		if command -v yay >/dev/null 2>&1; then \
			yay -S --needed $$(cat $(PACKAGE_DIR)/default-aur.txt); \
		elif command -v paru >/dev/null 2>&1; then \
			paru -S --needed $$(cat $(PACKAGE_DIR)/default-aur.txt); \
		else \
			printf "\e[31mNo AUR helper found. Install yay or paru first.\e[0m\n"; \
		fi; \
	else \
		printf "\e[33mNo default AUR packages found\e[0m\n"; \
	fi
	@printf "\e[33mInstalling host-specific AUR packages...\e[0m\n"
	@if [ -f "$(PACKAGE_DIR)/$(HOSTNAME)-aur.txt" ] && [ -s "$(PACKAGE_DIR)/$(HOSTNAME)-aur.txt" ]; then \
		if command -v yay >/dev/null 2>&1; then \
			yay -S --needed $$(cat $(PACKAGE_DIR)/$(HOSTNAME)-aur.txt); \
		elif command -v paru >/dev/null 2>&1; then \
			paru -S --needed $$(cat $(PACKAGE_DIR)/$(HOSTNAME)-aur.txt); \
		else \
			printf "\e[31mNo AUR helper found. Install yay or paru first.\e[0m\n"; \
		fi; \
	else \
		printf "\e[33mNo host-specific AUR packages found for $(HOSTNAME)\e[0m\n"; \
	fi
	@printf "\e[32mAUR package installation complete!\e[0m\n"

list-installed:
	@printf "\e[34mAll explicitly installed packages:\e[0m\n"
	@comm -23 <(pacman -Qqe | sort) <(pacman -Qqg base-devel | sort)
	@echo
	@printf "\e[34mAUR packages:\e[0m\n"
	@pacman -Qqem
