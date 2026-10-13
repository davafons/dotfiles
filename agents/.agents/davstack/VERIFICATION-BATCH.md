# Verification and control batch

## Delivered

This batch adds two global skills and the two remaining pstack playbooks at
`1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def`. Davstack now has 20 global development
skills and 23 playbooks. The complete upstream `control-cli` and
`maintain-verification-skill` methods and MIT licenses are retained. Runtime
adaptations cover native tools, private state, retained proof, jj, and authority.
No additional design protocols or generic UI controller were imported.

Three project-local verification skills live in `.agents/skills/` with links
from `.claude/skills/`. They reuse the existing Yuke, Herdr, and Neovim drivers.
The Herdr preparation helper stages source without build output and disables
sound and agent restoration in its copied configuration. Ten mapped features
were driven. Their generation proof is not a delegated maintenance audit.

The cleanup playbook now uses `dav-mode/scripts/workspace-audit.py`. The helper
fixes a jj operation and never snapshots, fetches, writes history, or deletes.
Its optional tracked-byte comparison can identify unsnapshotted edits, but does
not audit untracked/ignored state or unsaved buffers. PR and chat usage remain
unknown until separately evidenced. It never labels a workspace safe.

The Yuke source and installed `agent-tools/index.js` add a fresh `reviewer` role
on `openai-codex/gpt-6.1-sol` at `xhigh`. Existing general/dav-agent defaults are
unchanged. The choice follows the user's Codex-provider preference. Native
catalog discovery supports the selector and effort. This is not a measured
best-model claim. Spawn output retains engine-accepted model receipts, and child
request hooks log their selected models. The installed predecessor was checked
before replacement and backed up. No active reload occurred.

## Verification

Receipts and the append-only decision log are under:

```text
~/.cache/davstack/reviews/verification-batch/1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def/
```

The cache contains commands/results and pointers to driver-owned artifacts:

- `baseline-check.log` records 38 passing tests and ShellCheck before edits.
- `portable-link-first.log`, `portable-link-second.log`, and
  `portable-install-check.log` record actual installation. Initial
  `portable-check.log` failed two old expected-installation-set fixtures. Their
  behavioral expectations were extended for the two additions, and
  `portable-check-green.log` passed all 38 tests.
- `yuke-evidence-path.txt`, `herdr-evidence-path.txt`, and
  `neovim-evidence-path.txt` point to retained Doctor and drive logs. Yuke proved
  composer/reload in both motion variants, model controls, and build/status
  rendering. Herdr proved Code ordering, all indexed shortcut banks, and silent
  Yuke clarification notifications. Neovim proved pickers/completion, diff review,
  and Markdown rendering. Evidence survived driver teardown. The Neovim Doctor
  library pattern was corrected to the observed underscore filename before use.
- `herdr-muted-evidence-path.txt` retains a later initial multi-editor Code-order
  timeout with successful hook logs and reversed editor order. Its private server
  stopped. After a fresh Doctor, `herdr-muted-retry-evidence-path.txt` retains a
  passing fresh-instance repeat. The staging helper now explicitly disables sound
  in both copied config and the Code-order guard's own fixture config. No product
  or original guard edits occurred. The retry does not prove stability; task
  `w-b6d80bcefa2d4e20` tracks the observed intermittency.
- `workspace-audit-tests.log` records three actual private-jj tests. They check
  unsnapshotted byte differences, exact odd workspace paths, pinned/unknown usage,
  invalid inputs, unchanged operation history, and preserved files.
  `current-workspace-audit.json` is an audit-only observation of this checkout.
- `model-catalog-path.txt` points to isolated native catalog receipts with a
  dummy noncredential. The first diagnostic used numeric RPC IDs and failed;
  documented string IDs worked. It did not authenticate or call a real model.
- `agent-tools-check-final.log` and `installed-agent-tools-check.log` point to
  native child-routing runs from source and installed bytes. Each covers omitted
  role, general, dav-agent, and reviewer. Actual tool output, child session
  settings, stored history configs, HTTP model/effort payloads, depth limits, and
  native global/project-skill discovery agree. `agent-tools-predecessor-red.log` records
  a frozen predecessor failing the new runtime receipt contract. No shared source
  rollback occurred.
- The first routing fixture omitted a Responses endpoint still required by
  unmodified baked Codex models and was rejected as an invalid route. It now
  retains both endpoint protocols and explicitly selects Chat for its scripted
  models. A subsequent `session.config.get` probe returned unknown method from
  the installed binary; stored configs are instead read through the functioning
  `session.history` API. Both failed receipts are retained. Native core and SDK
  files were not edited.
- `installed-agent-tools-receipt.json` records the guarded atomic installation,
  backup, byte equality, and absence of active reload.
- `yuke-final-evidence-path.txt` points to final full-profile verification after
  the role edit. Both motion modes passed types, startup, input, native reload,
  disposal, and headless initialization in private homes.
- `final-link-first.log`, `final-link-second.log`, `final-installed-check.log`,
  and `final-check.log` record final link/link/check and 41 passing repository
  tests plus ShellCheck.

The native routing fixture is a scripted localhost provider, not a simulated
review verdict. It proves engine plumbing and cleanup, not LLM judgment, real
Codex authentication, or model-family diversity. Its result explicitly says
real model calls were zero. Comment/style review was direct and scoped to this
batch, not an independent review. No tests of skill prose, metadata, or reference
structure were added. Local link/syntax validation is a one-off installation
check, not a behavior suite or model evaluation.

## Open gates

- Cursor's built-in `create-skill` source/workflow is not installed. The authoring
  playbook preserves that dependency. Its general draft/test/iterate and
  description-optimization adapter is still missing. The proven verification
  generator is not a replacement for it.
- Codex-only reviewers cannot satisfy a different-model-family gate against an
  OpenAI implementer. Non-author model judgment has not run in this batch either.
  A configured role and scripted routing proof are not an independent verdict.
- Full transcript auditing for this conversation is not exposed by the current
  tools. The trail can be checked against available turns and retained receipts,
  not called a complete recovered transcript audit.
- Live maintenance's independent source-reader wave has not run. All mapped
  drives passed, but that alone is not a complete upstream maintenance result.
- Cleanup still needs actual pinned/active usage, PR evidence, disk inventory,
  preserved state, and concrete deletion approval. No user workspace, simulator, or
  cache cleanup ran, and no reclaimed-space claim is made.

The active process still has its old plugin catalog. Save the draft, wait for
active work to finish, then reload or restart deliberately. Another chat in the
same old process does not activate a new role. No GUI activation, system-wide
input, clipboard change, audio playback, credential copying, external posting,
push, merge, or deploy was performed. Prior Hillclimb and concurrent Yuke/Peek/
Herdr changes remain separate from this batch.
