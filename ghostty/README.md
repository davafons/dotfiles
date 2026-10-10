# Read rendered Markdown in Ghostty

Install the viewer on macOS:

```sh
brew install mcat
```

For image rendering, keep Chrome, Chromium, or Edge installed. If none is available,
let mcat download Chromium:

```sh
mcat --fetch-chromium
```

Open a native Ghostty split beside the editor. Run the rendered viewer in that split:

```sh
mcat notes.md -I --kitty
```

Use `h`, `j`, `k`, and `l` to pan. Use `+` and `-` to zoom, `0` to reset,
`g` and `G` to jump to the start or end, and `q` to quit.
After saving edits, quit and rerun the command to reload the document.
For selectable terminal text instead of an image, run:

```sh
mcat notes.md -c -p
```

To check image rendering without opening a window, save a PNG:

```sh
mcat notes.md -o image --silent > /tmp/markdown-preview.png
file /tmp/markdown-preview.png
```

Test in a native Ghostty split before trying a Herdr or tmux pane.
For options, run `mcat --help` or consult the [upstream documentation](https://github.com/Skardyy/mcat).
