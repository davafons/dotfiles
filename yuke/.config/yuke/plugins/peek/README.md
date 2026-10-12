# Peek

Peek explains a running session without sending input to its coding agent.

This plugin needs a Yuke build with `client.modelComplete`. It does not work with an older installed binary. It uses the manifest plugin API. Do not load it into a profile that still uses `index.js` instead of `config.json`.

## Load it

Copy this folder into a compatible profile's `plugins/peek` folder. Add `"./plugins/peek"` to `config.json`'s `plugins` list. Keep the existing entries. Restart Yuke after a native binary change. Save your draft before a later `/reload`.

The implementation is not enabled in your normal profile by its presence in this repository.

## Use it

Open a saved session. Run `/peek` to use that session's model. Run `/peek <model selector>` to use another configured model, such as a cheaper model from your catalog. Peek does not select a cheaper model on its own.

The window shows the snapshot time, selected model, and an explanation. Type a question and press Enter. Follow-up questions use the same snapshot. They do not read later worker updates.

| Key | Action |
|---|---|
| Enter | Ask about this snapshot |
| Ctrl+R | Cancel the pending observer request, capture new evidence, and request a new explanation |
| Ctrl+C | Cancel only the observer request |
| Page Up / Page Down | Scroll the explanation |
| Esc | Close the window and cancel its observer request |

Refresh starts a new observer conversation. Closing the window or unloading the plugin drops its snapshot and conversation. Your worker draft and attachments remain unchanged.

## Limits

Peek collects at most 8,000 UTF-16 code units of evidence. It prioritizes the latest compaction summary, the earliest available task, the latest instruction, and the live draft. It then adds recent messages. It excludes reasoning and attachment bytes. Tool arguments and results are excerpts. Earlier messages may no longer be available after compaction. Snapshot capture does not wait for the worker to finish a tool or a message.

Each request sends the snapshot, your question, and at most two earlier observer exchanges. Peek drops older exchanges if the encoded prompt exceeds 120 KiB. Questions take at most 2,000 code units. The model gets an output limit of 1,024 tokens. The window retains at most three exchanges and excerpts answers above 4,000 code units.

A model call still costs tokens. It uses the selected provider and its existing credentials. It does not enter the worker's context or session usage totals. Peek creates no child or saved session. It declares no tools and runs no engine hooks. It cannot inspect files, run commands, or message the worker through its model request.

The explanation is a model's reading of partial evidence. It is not proof that a test passed or that the work is correct. Peek labels unfinished drafts and asks the model to state uncertainty. It does not provide completion percentages or an ETA.

## Verify it

From the repository root:

```sh
zig build test --seed 0 -Dtest-filter=peek
tsc -p plugins/peek/jsconfig.json
zig build -Doptimize=ReleaseFast
python3 tools/test-peek.py --binary zig-out/bin/yuke
```

The local-provider test uses a private temporary profile and a detached tmux server. It sends no paid model requests and does not use your normal session store or provider credentials.
