# Solarized theme

The profile loads `plugins/solarized-theme.js` at startup. Restart Yuke after an edit.

The dark theme uses Selenized foreground colors and the darker backgrounds configured in Ghostty and Alacritty. The light theme uses Solarized reading surfaces. The theme follows the terminal background and the detected color depth. It supplies separate palettes for RGB and 256-color terminals.

| Color | Use |
|---|---|
| Blue | UI titles, borders, prompts, status, Markdown headings, tool titles |
| Cyan | Tool arguments and code blocks |
| Yellow | Inline code and warnings |
| Violet | Reasoning |
| Green | Quotes and added lines |
| Red | Errors and deleted lines |
| Neutral | Body text, tool output, hints, and metadata |

Secondary text uses explicit colors. It does not use terminal dimming.

Your messages use a distinct muted teal background and warm light text. This makes each request easy to find in the history. Completed tool blocks use a softer green background and gray output text. Pending tools use an olive background. Failed tools use a red background. These backgrounds fill the row and stay with each block when you scroll. They do not follow a cursor.

The dark user-message surface is `#28434d`, sampled from David's Codex screenshot. It keeps the terminal's foreground blue. The user-message text has a contrast ratio of 8.57:1 on its background. Selection surfaces remain darker than user messages.

Edit `palettes` to change colors. Edit `groups` to change which parts use each color. The plugin changes style data at startup or when the terminal background or color depth changes. It adds no draw or transcript renderer callbacks.

Palette references: [Solarized](https://github.com/altercation/solarized) and [Selenized](https://github.com/jan-warchol/selenized).
