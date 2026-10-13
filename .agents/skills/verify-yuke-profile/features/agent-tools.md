# Child routing and reviewer model

## Sub-features

Default/general selection, dav-agent inheritance, reviewer selection, accepted
model and effort receipts, stored run settings, request model logs, and child
depth limits. Native discovery of the project verification skills.

## How to get to it (user POV)

Ask for a scoped delegated task or a fresh reviewer explicitly. The native
`spawn_agent` tool selects `general`, `dav-agent`, or `reviewer`. Source changes
appear only after installing the intentional edit and starting a fresh process
or performing an idle reload after saving the draft.

## Driving it with the repository driver

Run `python3 -B yuke/tests/check-agent-tools.py --binary "$YUKE_BIN" 2>&1 | tee "$EVIDENCE/agent-tools.log"`.
Require all four routing cases to PASS. Read its printed artifact directory,
`result.json`, native parent/child histories, RPC receipts, and `requests.json`.
The test goes through the native spawn tool and child engine, not an internal
setter. Check that its native process stopped and evidence survives cleanup.

## Gotchas

The local provider returns scripted literal replies. This proves routing and
receipt behavior, not LLM review quality, real Codex authentication, or different
model families. Do not count the fixture as an independent review. The reviewer
is GPT-6.1 Sol at xhigh; general remains GPT-6 Luna with its model default, and
dav-agent inherits the parent's model and effort. Read-only review is a brief,
not a sandbox. Other request hooks can alter the model after accepted settings;
inspect actual request evidence and child `CHILD_REQUEST_MODEL` logs too.
