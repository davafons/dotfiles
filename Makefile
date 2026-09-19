#!/usr/bin/make -f

DOTFILES_DIR := $(patsubst %/,%,$(dir $(abspath $(lastword $(MAKEFILE_LIST)))))
HOSTNAME ?= $(shell hostname)
STOW := stow
STOW_FLAGS := --no-folding
PACKAGE_DIR := packages
PROFILE ?= $(HOSTNAME)
PROFILE_FILE := $(DOTFILES_DIR)/profiles/$(PROFILE).mk

ifneq ($(wildcard $(PROFILE_FILE)),)
include $(PROFILE_FILE)
endif

PACKAGES ?= $(PROFILE_PACKAGES)

.PHONY: help bootstrap install uninstall plan status doctor check skills-sync upgrade-skills tools-status list list-profiles check-stow check-profile install-packages install-packages-non-aur install-packages-aur list-installed

# Default target
all: help

# Default goal
.DEFAULT_GOAL := help

help:
	@printf "\e[34mDotfiles Management with GNU Stow and Package Installation\e[0m\n"
	@echo "Usage: make [TARGET] [PROFILE=name] [PACKAGES=\"package1 package2 ...\"]"
	@echo ""
	@printf "\e[33mDotfiles Targets:\e[0m\n"
	@printf "  \e[32mplan\e[0m                Preview Stow changes for a profile\n"
	@printf "  \e[32mbootstrap\e[0m           Install dotfiles and provider skills, then verify\n"
	@printf "  \e[32minstall\e[0m             Install the selected profile\n"
	@printf "  \e[32muninstall\e[0m           Uninstall the selected profile\n"
	@printf "  \e[32mstatus\e[0m              Alias for plan\n"
	@printf "  \e[32mdoctor\e[0m              Check Stow and profile package definitions\n"
	@printf "  \e[32mcheck\e[0m               Run lightweight skill, shell, and wrapper tests\n"
	@printf "  \e[32mskills-sync\e[0m         Refresh externally managed provider skills\n"
	@printf "  \e[32mupgrade-skills\e[0m      Refresh skills embedded in installed provider CLIs\n"
	@printf "  \e[32mtools-status\e[0m        Show agent-facing CLI versions\n"
	@printf "  \e[32mlist\e[0m                List available dotfiles packages\n"
	@printf "  \e[32mlist-profiles\e[0m       List named profile manifests\n"
	@echo ""
	@printf "\e[33mSystem Package Targets:\e[0m\n"
	@printf "  \e[32minstall-packages\e[0m    Install default and host-specific packages\n"
	@printf "  \e[32minstall-packages-non-aur\e[0m Install only non-AUR packages\n"
	@printf "  \e[32minstall-packages-aur\e[0m Install only AUR packages\n"
	@printf "  \e[32mlist-installed\e[0m      List currently installed packages\n"
	@printf "  \e[32mshow-config\e[0m         Show current configuration\n"
	@printf "  \e[32mhelp\e[0m                Show this help message\n"
	@echo ""
	@echo "Selected profile: $(PROFILE)"
	@echo "Profile manifest: $(PROFILE_FILE)"
	@echo "Packages: $(PACKAGES)"

plan: check-stow check-profile
	@echo "Planned packages for profile '$(PROFILE)': $(PACKAGES)"
	@set -eu; for package in $(PACKAGES); do \
		test -d "$(DOTFILES_DIR)/$$package" || { echo "Package '$$package' not found" >&2; exit 1; }; \
		echo "Planning $$package..."; \
		$(STOW) $(STOW_FLAGS) -n -v -d "$(DOTFILES_DIR)" -t "$(HOME)" "$$package"; \
	done

bootstrap: install
	@case " $(PACKAGES) " in \
		*" agents "*) $(MAKE) skills-sync PROFILE="$(PROFILE)" ;; \
		*) echo "Profile '$(PROFILE)' does not install personal agent skills; skipping provider skill sync." ;; \
	esac
	@$(MAKE) check PROFILE="$(PROFILE)"
	@$(MAKE) doctor PROFILE="$(PROFILE)"

install: check-stow check-profile
	@echo "Installing profile '$(PROFILE)': $(PACKAGES)"
	@set -eu; for package in $(PACKAGES); do \
		test -d "$(DOTFILES_DIR)/$$package" || { echo "Package '$$package' not found" >&2; exit 1; }; \
		echo "Installing $$package..."; \
		$(STOW) $(STOW_FLAGS) -R -v -d "$(DOTFILES_DIR)" -t "$(HOME)" "$$package"; \
	done
	@case " $(PACKAGES) " in \
		*" agents "*) "$(DOTFILES_DIR)/bin/bin/agent-skills" link ;; \
	esac
	@echo "Installation complete!"

uninstall: check-stow check-profile
	@echo "Uninstalling profile '$(PROFILE)': $(PACKAGES)"
	@set -eu; for package in $(PACKAGES); do \
		test -d "$(DOTFILES_DIR)/$$package" || { echo "Package '$$package' not found" >&2; exit 1; }; \
		echo "Uninstalling $$package..."; \
		$(STOW) $(STOW_FLAGS) -v -d "$(DOTFILES_DIR)" -t "$(HOME)" -D "$$package"; \
	done
	@echo "Uninstallation complete!"

status: plan

doctor: check-stow check-profile
	@set -eu; for package in $(PACKAGES); do \
		test -d "$(DOTFILES_DIR)/$$package" || { echo "Missing package: $$package" >&2; exit 1; }; \
	done
	@echo "Profile '$(PROFILE)' is valid. Run 'make plan PROFILE=$(PROFILE)' to check its Stow links."
	@case " $(PACKAGES) " in \
		*" agents "*) "$(DOTFILES_DIR)/bin/bin/agent-skills" check ;; \
	esac

check:
	@shellcheck "$(DOTFILES_DIR)/bin/bin/playwright-cli" "$(DOTFILES_DIR)/bin/bin/playwright-brave-launcher" "$(DOTFILES_DIR)/bin/bin/agent-skills" "$(DOTFILES_DIR)/bin/bin/codex-mcp-grafana"
	@python3 -m unittest -v bin/tests/test_playwright_focus.py
	@validator="$(HOME)/.codex/skills/.system/skill-creator/scripts/quick_validate.py"; \
	if [ -f "$$validator" ]; then \
		for skill in browser calendar mail notes plan tasks; do python3 "$$validator" "$(DOTFILES_DIR)/agents/.agents/skills/$$skill"; done; \
	fi

skills-sync:
	@"$(DOTFILES_DIR)/bin/bin/agent-skills" sync

upgrade-skills: skills-sync
	@echo "Provider skills now match the currently installed CLIs. Binary upgrades remain provider-specific."

tools-status:
	@"$(DOTFILES_DIR)/bin/bin/agent-skills" status

list:
	@echo "Available packages:"
	@for path in "$(DOTFILES_DIR)"/*; do \
		[ -d "$$path" ] || continue; \
		name="$${path##*/}"; \
		case "$$name" in packages|profiles) continue ;; esac; \
		echo "$$name"; \
	done | sort

list-profiles:
	@for profile in "$(DOTFILES_DIR)"/profiles/*.mk; do \
		[ -f "$$profile" ] || continue; \
		name="$${profile##*/}"; echo "$${name%.mk}"; \
	done | sort

check-stow:
	@command -v $(STOW) >/dev/null 2>&1 || { \
		echo "Error: GNU Stow is not installed."; \
		echo "Please install it using your package manager:"; \
		echo "  Ubuntu/Debian: sudo apt install stow"; \
		echo "  Arch Linux: sudo pacman -S stow"; \
		echo "  macOS: brew install stow"; \
		exit 1; \
	}

check-profile:
	@test -f "$(PROFILE_FILE)" || { \
		echo "Unknown profile '$(PROFILE)'. Run 'make list-profiles'." >&2; \
		exit 1; \
	}
	@test -n "$(strip $(PACKAGES))" || { \
		echo "Profile '$(PROFILE)' has no packages." >&2; \
		exit 1; \
	}

# Package management targets
install-packages: check-profile
	@if [ "$(PROFILE_OS)" = "macos" ]; then \
		command -v brew >/dev/null 2>&1 || { echo "Homebrew is not installed" >&2; exit 1; }; \
		brew bundle install --file "$(DOTFILES_DIR)/$(PACKAGE_DIR)/Brewfile"; \
	elif [ "$(PROFILE_OS)" = "linux" ]; then \
		$(MAKE) install-packages-non-aur install-packages-aur PROFILE="$(PROFILE)"; \
	else \
		echo "Profile '$(PROFILE)' has unknown PROFILE_OS='$(PROFILE_OS)'" >&2; exit 1; \
	fi
	@printf "\e[32mAll package installation complete!\e[0m\n"

# Install only non-AUR packages
install-packages-non-aur:
	@printf "\e[34mInstalling non-AUR packages for profile: $(PROFILE)\e[0m\n"
	@echo "=================================="
	@printf "\e[33mInstalling default packages...\e[0m\n"
	@if [ -f "$(PACKAGE_DIR)/default.txt" ] && [ -s "$(PACKAGE_DIR)/default.txt" ]; then \
		sudo pacman -S --needed $$(cat $(PACKAGE_DIR)/default.txt); \
	else \
		printf "\e[31mNo default packages found\e[0m\n"; \
	fi
	@printf "\e[33mInstalling profile-specific packages...\e[0m\n"
	@if [ -f "$(PACKAGE_DIR)/$(PROFILE).txt" ] && [ -s "$(PACKAGE_DIR)/$(PROFILE).txt" ]; then \
		sudo pacman -S --needed $$(cat $(PACKAGE_DIR)/$(PROFILE).txt); \
	else \
		printf "\e[33mNo profile-specific packages found for $(PROFILE)\e[0m\n"; \
	fi
	@printf "\e[32mNon-AUR package installation complete!\e[0m\n"

# Install only AUR packages
install-packages-aur:
	@printf "\e[34mInstalling AUR packages for profile: $(PROFILE)\e[0m\n"
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
	@printf "\e[33mInstalling profile-specific AUR packages...\e[0m\n"
	@if [ -f "$(PACKAGE_DIR)/$(PROFILE)-aur.txt" ] && [ -s "$(PACKAGE_DIR)/$(PROFILE)-aur.txt" ]; then \
		if command -v yay >/dev/null 2>&1; then \
			yay -S --needed $$(cat $(PACKAGE_DIR)/$(PROFILE)-aur.txt); \
		elif command -v paru >/dev/null 2>&1; then \
			paru -S --needed $$(cat $(PACKAGE_DIR)/$(PROFILE)-aur.txt); \
		else \
			printf "\e[31mNo AUR helper found. Install yay or paru first.\e[0m\n"; \
		fi; \
	else \
		printf "\e[33mNo profile-specific AUR packages found for $(PROFILE)\e[0m\n"; \
	fi
	@printf "\e[32mAUR package installation complete!\e[0m\n"

list-installed:
	@printf "\e[34mAll explicitly installed packages:\e[0m\n"
	@comm -23 <(pacman -Qqe | sort) <(pacman -Qqg base-devel | sort)
	@echo
	@printf "\e[34mAUR packages:\e[0m\n"
	@pacman -Qqem
