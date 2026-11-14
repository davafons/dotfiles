# Composer input and reload

## Sub-features

Dashboard, Vim editing, path completion, panes, reload, recorded direct commands, masked sudo, context and usage dialogs, tasks, search, clarification adoption, and `/cd`.

## How to get to it (user POV)

Start `yuke`, edit the composer in Normal or Insert mode, complete a path after `/cd `, open panels, and run `/reload` after a run ends. Save any real draft before reloading the user's session.

## Driving it with the repository driver

Run `YUKE_BINARY="$YUKE_BIN" python3 -B yuke-rust/tests/terminal.py 2>&1 | tee "$EVIDENCE/terminal.log"`. Require its final `PASS real terminal` line. The raw transcript is written to `$YUKE_VIM_TERMINAL_LOG` (default `/tmp/yuke-vim-terminal.log`). For Vim alone, run `"$YUKE_BIN" test yuke-rust/.config/yuke-rust/plugins/vim/tests`.

## Gotchas

The driver copies the checkout's profile into a private home and syncs `plugins.lock`, so Git plugins such as btw need network access to GitHub. Its provider refuses every model request. The sudo fixture runs as the current user and never invokes real sudo.
