# Install Karakeep MCP

The `bin` Stow package installs `~/bin/karakeep-mcp` on the Mac and Tower.
The launcher runs `@karakeep/mcp@0.34.0` through `npx` and connects to
`https://board.davafons.cc`. Install Node.js and npm on each machine first.

From the dotfiles checkout, install the launcher:

```sh
make install PROFILE=mb PACKAGES=bin
```

On Tower, use `PROFILE=tower` instead.

## Configure credentials

The launcher uses `KARAKEEP_API_KEY` if set, then
`${XDG_CONFIG_HOME:-$HOME/.config}/karakeep/api-key`, then macOS Keychain.
The Mac already has the Keychain item `com.davafons.codex.mcp-karakeep` under
the current username. Keep that item when moving the launcher.

On Tower, save the key outside the checkout. Run these commands in Bash to
prompt without echoing the key or putting it in shell history:

```bash
mkdir -p "${XDG_CONFIG_HOME:-$HOME/.config}/karakeep"
chmod 700 "${XDG_CONFIG_HOME:-$HOME/.config}/karakeep"
read -r -s -p 'Karakeep API key: ' karakeep_key
printf '\n'
(umask 077; printf '%s\n' "$karakeep_key" > "${XDG_CONFIG_HOME:-$HOME/.config}/karakeep/api-key")
unset karakeep_key
chmod 600 "${XDG_CONFIG_HOME:-$HOME/.config}/karakeep/api-key"
```

Set `KARAKEEP_API_ADDR` to override the server address.

## Register with Claude Code

Run this on each machine after installing the launcher and credentials:

```sh
claude mcp add --scope user --transport stdio karakeep -- "$HOME/bin/karakeep-mcp"
claude mcp get karakeep
```

Restart Claude Code and check `/mcp` for the connection status.

## Register with Codex

Add this block to `~/.codex/config.toml`, using the machine's absolute home path:

```toml
[mcp_servers.karakeep]
command = "/Users/davafons/bin/karakeep-mcp"
```

On Tower, replace `/Users/davafons` with its home path. Restart Codex after
changing the configuration. The existing Mac configuration uses
`~/.local/bin/karakeep-mcp`, which now links to the launcher in this checkout.
