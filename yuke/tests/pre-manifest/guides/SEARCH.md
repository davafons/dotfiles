# Native search

Run `/search` or `/search words`. Search opens a native result list with a preview. It does not replace Ctrl+F or the session browser.

## Controls

| Key | Action |
|---|---|
| Up/Down or Ctrl+P/Ctrl+N | Select a result. |
| Tab | Switch between workspace and all-session scope. |
| Ctrl+T | Switch between All, Chats, and Files. |
| Enter | Open a chat/session or insert a file path. |
| Ctrl+Y | Insert the previewed passage or file path. |
| Ctrl+D/Ctrl+U | Scroll the preview. |
| Ctrl+R | Refresh. |
| Escape or Ctrl+C | Close without changing the draft. |

Insertion keeps the existing draft and uses its caret. No action sends a message or calls a model. A narrow terminal shows only the result list.

## Find the useful text

Chat search reads saved user prompts and assistant answers. It excludes reasoning, tool output, images, and compaction summaries. It does not estimate importance with a model.

Words match token prefixes. Multiple words must occur in the same text part. For example, `owner lock` matches `ownership locks`. This is word search, not semantic search or fzf syntax.

Matching passages appear before session titles and file paths. A long message previews the best matching passage with context, rather than its first page. Ctrl+Y inserts that passage, so a quote does not lose a match near the end of a long message. A title-only result remains available when no passage in that session matches. Empty search lists recent sessions and workspace paths.

File search matches both fuzzy paths and literal file content. Lowercase content queries ignore case. A query with uppercase letters matches case. Content search starts at two characters. Ripgrep applies its normal ignore rules. Hidden and binary content stays excluded by default. A preview cannot follow a path or symlink outside the workspace.

Workspace scope uses the current session's workspace, or the launch folder for a draft. All-session scope includes saved chats across workspaces. It does not scan every workspace's files. Root sessions and forks are included. Child-agent sessions stay in the agent picker.

Chat badges use cyan. File badges use green. Session badges use violet when the theme supplies it. Matching preview terms use yellow, bold text, and an underline. Progress uses yellow. Ready state uses green. Failures use red. These groups use the active palette.

## Open a result

Search shares discovery and ownership checks with the session browser. It checks ownership again on Enter. A locally available session opens in the current pane. A foreign-owned session jumps to its reported Herdr pane through the existing integration. Missing owners and failed jumps leave search open with an error.

Enter opens the session, not the exact message position. A Herdr jump focuses the owning pane. Use Ctrl+Y to keep the matching passage in your draft instead. File-content results insert a quoted absolute path with its line number.

## Index and errors

One Python worker runs while search is open. Closing search or unloading the plugin stops it. Closed search does not scan files or update the index.

The private, rebuildable index lives at `$XDG_CACHE_HOME/$YUKE_APPNAME/search/history-v1.db`, normally `~/.cache/yuke/search/history-v1.db`. It contains copies of saved chat text, which can include private information. New cache files use mode 0600. The search directory uses mode 0700. The plugin does not upload the index.

Yuke's public session APIs supply the index. The helper does not read Yuke's private database. Later opens reuse unchanged histories. Refresh removes deleted sessions and replaces changed histories atomically. A partial read does not mark a chat ready.

The first open shows indexing progress. Results remain partial until it finishes. If a chat changes during the read, search retries it once. A chat that keeps changing shows as updating, not as unindexable. Saved message commits trigger another refresh while the finder is open. A real failure shows its reason in red. Ctrl+R retries it. The Yuke log keeps the session ID and error.

Limits:

- All shows at most 30 chat passages, 30 file-content matches, 20 paths, and 20 session titles. Chats allows 60 passages and 20 title results. Files allows 40 content matches and 40 paths. A passage result suppresses a duplicate title result for the same session.
- File discovery keeps at most 20,000 paths until refresh. File queries have a five-second deadline.
- A long chat previews up to 64 words around the match. A short chat previews up to 4,000 characters. A quote inserts at most 8,000 characters.
- File previews show at most 100 lines and stop at a line above 16 KiB.
- Chat queries accept at most 16 words. History reads stop with an error after 1,000 pages of 20 messages.
- Helper requests have a 30-second deadline. Oversized host pipe writes or responses fail visibly.

Install `python3` with SQLite FTS5 support and `rg`. If the cache is damaged, close search and remove its cache directory. The next open rebuilds it.

## Checks

```sh
python3 ~/.config/yuke/tests/check-search-store.py
python3 ~/.config/yuke/tests/check-search-tui.py
python3 ~/.config/yuke/tests/check-sessions-reworked.py
tsc -p ~/.config/yuke/jsconfig.json
yuke check
```

The TUI check uses detached tmux, a temporary profile/index, and a mock Herdr socket. It checks colors, history retries, draft safety, and worker cleanup. It does not change desktop focus, use the clipboard, or send a model request.

Run `/reload` in the normal profile after a plugin change. The resident profile loader reloads the registrations. The helper starts from its current file on the next search open.
