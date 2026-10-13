# Peek

Peek explains a running session without sending input to its coding agent.

This plugin needs a Yuke build with `client.modelComplete` and `client.sessionLastRun`. It does not work with an older installed binary. It uses the manifest plugin API. Do not load it into a profile that still uses `index.js` instead of `config.json`.

## Load it

Copy this folder into a compatible profile's `plugins/peek` folder. Add `"./plugins/peek"` to `config.json`'s `plugins` list. Keep the existing entries. Restart Yuke after a native binary change. Save your draft before a later `/reload`.

The implementation is not enabled in your normal profile by its presence in this repository.

## Use it

Open a saved session. Run `/peek` to use that session's model. Run `/peek <model selector>` to use another configured model, such as a cheaper model from your catalog. Peek does not select a cheaper model on its own.

The window shows captured facts before the model answers. The facts include current activity, queued inputs, the last completed turn outcome, recent check commands, recorded file changes, tool states, and reported errors. The model adds a separate summary of completed work, work in progress, blockers, and next steps.

Type a question and press Enter. Follow-up questions use the same frozen snapshot. They do not read later worker updates.

| Key | Action |
|---|---|
| Enter | Ask about this snapshot |
| Ctrl+R | Cancel the pending observer request, capture new evidence, and request a new explanation |
| Ctrl+C | Cancel only the observer request |
| Page Up / Page Down | Scroll the explanation |
| Esc | Close the window and cancel its observer request |

Refresh compares the new capture with the previous snapshot and starts a new observer conversation. The comparison names newly visible and updated action records. It does not claim a complete change history. Closing the window or unloading the plugin drops its snapshot and conversation. Your worker draft and attachments remain unchanged.

Recorded file changes come from completed tools' diff metadata. Peek shows short path and hunk excerpts without reading the working directory or running a command. Shell edits and other changes without recorded diffs can be absent. These excerpts do not describe the current worktree state.

The last completed turn can precede the current live activity. A failed turn without an assistant message still appears there. It does not describe the outcome of an unfinished turn.

A check's exit code describes the whole shell command. It does not prove that every test passed. A completed tool call does not mean the task is finished. Missing check results and file changes stay unknown.

## Limits

Peek collects at most 8,000 UTF-16 code units of evidence. It prioritizes the latest compaction summary, the earliest available task, the latest instruction, and the live draft. It then adds recent messages. It excludes reasoning and attachment bytes. Tool arguments and results are excerpts. Earlier messages may no longer be available after compaction. Snapshot capture does not wait for the worker to finish a tool or a message.

A capture also keeps at most 12 tool action records, six recorded files, and three error excerpts. Each file shows at most four lines from its first diff hunk. Paths take at most 200 code units. Diff lines take at most 120. Command labels and result tails take at most 240. Peek can miss actions outside these excerpts. It marks omitted data.

Each request sends these captured facts, the transcript excerpts, your question, and at most two earlier observer exchanges. Peek drops older exchanges if the encoded prompt exceeds 120 KiB. Questions take at most 2,000 code units. The model gets an output limit of 1,024 tokens. The window retains at most three exchanges and excerpts answers above 4,000 code units.

A model call still costs tokens. It uses the selected provider and its existing credentials. It does not enter the worker's context or session usage totals. Peek creates no child or saved session. It declares no tools and runs no engine hooks. It cannot inspect files, run commands, or message the worker through its model request.

The explanation is a model's reading of partial evidence. It is not proof that a test passed or that the work is correct. Peek labels unfinished drafts and asks the model to state uncertainty. It does not provide completion percentages or an ETA.

## Verify it

Check the installed plugin against the profile declarations:

```sh
tsc -p "$HOME/.config/yuke/plugins/peek/jsconfig.json"
```

Run the native guards from a Yuke source checkout:

```sh
zig build test --seed 0 -Dtest-filter=peek
zig build -Doptimize=ReleaseFast
python3 tools/test-peek.py --binary zig-out/bin/yuke
python3 tools/test-peek.py --binary "$HOME/.local/bin/yuke" --profile "$HOME/.config/yuke"
```

The local-provider test uses a private temporary profile and a detached tmux server. It sends no paid model requests and does not use your normal session store or provider credentials.
