# Native skill-authoring port

## Delivered

The user approved the complete public Anthropic skill-creator as the native
replacement dependency for Cursor's unpublished `create-skill`. The source is
`anthropics/skills` at `dbd4588f9e1033efb41dad4bef2f7947c8993d44`, licensed under
Apache-2.0. Cursor's official skills documentation confirms its built-in exists,
but does not supply its implementation. This port does not claim to recover it.

All 18 source files are retained. Thirteen are byte-identical, including license,
agent prompts, schemas, HTML assets, packaging, aggregation and report helpers.
Five have native/runtime/authority changes. `NOTICE.md` identifies them. The
ordered intent, draft, paired evaluation, grading, human review, feedback,
iteration, optional blind comparison and description optimization methods remain.

The native helpers target Yuke on macOS, including the existing Codex provider.
They use private HOME, workspace, data, state and cache. Authentication is read
by the native application from the existing config; credentials are not copied.
macOS sandbox-exec denies filesystem writes outside the trial and blocks common
GUI, clipboard and audio launch commands. This is write isolation, not an
unrestricted-skill, credential-read or comprehensive network security sandbox.
Only trusted, scoped test prompts were used. No active profile/session reload.

Every trial uses an explicit model, at most 60 seconds and native max_rounds=8.
An authorized locked budget includes failed/timed-out sessions and cannot grow
or silently retry. Model failures are inconclusive, not false nontriggers that
could earn correct negative-query scores. Trigger trials observe the completed
first tool decision, then cancel their owned run. Content trials require normal
completion and actual outputs. The viewer no longer auto-opens a browser or
kills an unrelated process by port.

The installer registers the complete skill directory for Yuke/Codex and Claude.
Davstack now has 21 global development skills and 23 playbooks. The authoring
playbook and substantive/description `reflect` routes use `skill-creator`, with
existing edit-approval and execution gates. Verification generation remains its
specialized separate workflow. Herdr ordering work was not part of this port.

## Evidence

Receipts live under:

```text
~/.cache/davstack/reviews/native-authoring/dbd4588f9e1033efb41dad4bef2f7947c8993d44/
```

- `source.json`, `tree.json`, and `port-source-receipt.json` identify the full
  pinned source, original hashes, byte-identical files and modifications.
- The macOS sandbox Doctor verified an allowed inside write and a denied outside
  write before model execution. Native localhost transport verified actual
  catalog visibility, RPC limits, history and stopped process behavior.
- `native-behavior-tests.log` records three native behavior tests. They verify
  completed skill reads and owned cancellation, normal answers without a read,
  refusal before a request after budget exhaustion, and provider failure as
  inconclusive. No real models are called by these tests.
- A scripted native two-iteration fixture exercised the actual train/holdout
  split, blinded optimizer history, description proposal, reevaluation and saved
  report. Its synthetic replies prove orchestration, not model effectiveness.
- `live/budget.json` records exactly eight of eight authorized real sessions.
  Each `live/run-*/result.json` names accepted model/settings, native engine,
  outcome or error, scope, history and process cleanup. Every process stopped.
  Successful histories identify `openai-codex/gpt-6.1-sol` at `high`.
- Real baseline and admitted-skill CSV trials both produced exact numeric totals
  and left the input bytes unchanged. A successful natural positive query read
  the temporary skill; a negative conceptual query answered without that read.
  A real description proposal and one proposed-description reevaluation ran.
  The proposal remains an artifact, not an applied change to a real skill.
- One early positive trial timed out because the first transport waited for task
  completion after a successful skill read. Its result remains INCONCLUSIVE.
  The port was corrected to upstream's early-selection observation. Fresh trials
  passed with completed-read evidence and owned cancellation. A temporary probe
  also lacked Python's multiprocessing main guard; it was corrected, and worker
  errors were not converted into successful negative scores.
- `content-review/iteration-1/` contains copies of actual task outputs, native
  histories, direct grades and timing. `content-review/review.html` is the saved
  upstream static reviewer. Its benchmark metadata is explicitly one serial
  run per side, not the upstream default placeholder of three. The page marks
  all performance/effectiveness comparisons inconclusive. No browser was opened
  and no human feedback was fabricated.
- `native-catalog-path.txt` points to a cold native installed-skill catalog proof
  without a model turn. `link-first.log`, `link-second.log`, `installed-check.log`
  and `check.log` record successful link/link/check and 44 tests plus ShellCheck.

The eight-run grant is consumed. It must not be reset or reused. All failures and
partial observations remain in the evidence directory. There are no tests of
skill prose, metadata, or reference structure. Comment/style review was direct
and scoped, not an independent reviewer verdict.

## Limits and follow-up

The port is installed and its native task/selection/proposal paths were exercised.
That is not a full authoring campaign. Human feedback, further content revisions,
expanded examples, the full 20-query repeated description campaign, and a real
independent blind judge have not run. Single positive/negative smoke queries do
not establish general selection accuracy or optimal description wording. Single
serial content trials do not establish a quality improvement or performance win.

Selection observations use an isolated temporary catalog/stub and scoped policy,
not the complete instructions/competing catalog of the user's active chat. A
real target campaign must use representative context and approve its test set,
model budget and concurrency. Other frontends or operating systems need their
own verified transport; no unsafe fallback is supplied. Existing cross-family
requirements remain open under Codex-only model availability.

No native core/SDK edits, provider changes, credential copies, user-data changes,
GUI activation, system-wide input, clipboard/audio operations, external posting,
push, merge, deploy, or shared history restructuring were performed. Concurrent
Neovim, Yuke, Peek and Herdr work remains outside this port.
