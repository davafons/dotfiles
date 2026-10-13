# Run the skill-creator on the native runtime

## Source and scope

The full method and supporting files come from Anthropic's skill-creator at
`dbd4588f9e1033efb41dad4bef2f7947c8993d44`, under Apache-2.0. Cursor documents its
built-in `/create-skill` but does not publish that body on its skills page. The
user approved this public workflow as the native dependency. Do not describe it
as a recovered Cursor implementation.

The model helpers target Yuke on macOS, including Codex-provider models. A
Claude/Codex frontend can call them, but their selection observations still
measure Yuke. No Linux, standalone Codex, or Claude CLI backend is implied.

## Authorize a bounded run

Obtain explicit permission for the model sessions, their model, concurrency,
time, and round budget. Preparing files does not authorize fresh model runs.
Use an external private state directory and point the helpers at it:

```sh
export DAVSTACK_AUTHORING_ALLOW_MODELS=1
export DAVSTACK_AUTHORING_BUDGET="$STATE/budget.json"
export DAVSTACK_AUTHORING_EVIDENCE="$STATE"
```

A new authorized run gets a new directory and an explicitly approved
`{"limit": N, "used": 0}` budget. Preserve a consumed budget; do not reset it or
reuse its grant. Record the directory in the project's checkpoint.
The locked counter includes failed and timed-out sessions. It never silently
retries or grows the allowance. Default execution is serial. Parallel workers
need explicit authorization before `--num-workers` is increased.

Every model trial requires an explicit `provider/model` selector. The native
transport uses the existing config for authentication without copying provider
files or keys. HOME, data, state, cache, and workspace are private. macOS
sandbox-exec denies filesystem writes outside the trial root and blocks common
GUI, clipboard, and audio launch commands. This is write isolation, not a claim
of credential-read or comprehensive network/tool sandboxing. Use trusted trial
prompts. Do not grant arbitrary untrusted skills this execution path.

Timeouts are at most 60 seconds and native `max_rounds` is eight. Missing Yuke,
sandbox support, model authorization, or budget fails closed. If authentication
requires a refresh write outside the private root, report it blocked; do not
change credentials or weaken isolation to get a pass.

## Run paired content trials

From the skill-creator directory, use `scripts.native_model.run_trial`. Pass the
same task and input fixtures to candidate and baseline. A candidate supplies
`skill_name`, complete `skill_content`, and `admit_skill=True`; admission uses
native input metadata, not concatenated hidden instructions. A new-skill baseline
supplies no skill. An existing-skill baseline supplies its preserved predecessor.

The native result identifies `artifact_dir`, accepted `session`, stored
`history_config`, actual `outcome`, text, observed tokens, and duration. Read
`history.json`, `rpc.jsonl`, `stderr.log`, and `result.json`. `work/` contains actual
task files. Failed evidence survives process cleanup. Copy only requested output
files into the upstream iteration/eval/with_skill or baseline `outputs/` layout.
Do not expose the skill source or internal stores as task outputs to a blind
judge. Save transcript and timing records beside the outputs, not inside them.

Use the full grader, analyzer, and optional comparator templates. Programmatic
checks inspect actual task outputs. Subjective judgments need human review; no
prose-text assertions stand in for skill effectiveness. Review the parent
workflow's independence and family gates before any comparison. Serial smoke
runs are not the simultaneous multi-agent baseline benchmark.

## Run description selection and optimization

The existing `scripts.run_eval` interface is preserved. Native trials register
an isolated temporary skill with the proposed description and the upstream stub
body. Natural user queries do not explicitly admit the skill. The observer records
the completed first tool operation. A completed `read` of that exact skill file
is a trigger; another successful first tool or a normal answer without a read
is a nontrigger. A failed request, failed first tool, exhausted budget, or timeout
is inconclusive and aborts scoring. Infrastructure errors cannot become correct
negative-query scores.

After the first observed tool decision, the transport cancels the owned trial
and retains its actual tool record and history. It does not need to finish the
user task to measure the selection decision. Content trials still require a
normal completed turn and real task outputs.

`scripts.improve_description` keeps the full upstream prompt, failure analysis,
history, generalization instructions, length bound, and retained proposal record.
Its model call uses the same native transport. `scripts.run_loop` retains the
stratified train/holdout split, repeated trials, blinded proposal history, final
selection, and report schema. The bounded smoke did not run that full campaign.
Plan and approve its total sessions first. The normal 20-query, three-repeat,
up-to-five-iteration campaign requires its own explicit campaign budget.

Do not automatically apply a proposed description to an existing real skill.
Honor `reflect`'s Accepted-edit approval gate and show actual before/after
behavior evidence. A successful single trial does not establish optimal wording.

## Review without taking desktop focus

Use the upstream aggregation and viewer helpers:

```sh
python3 -m scripts.aggregate_benchmark "$ITERATION" --skill-name "$NAME"
python3 eval-viewer/generate_review.py "$ITERATION" --skill-name "$NAME" \
  --benchmark "$ITERATION/benchmark.json" --static "$STATE/review.html"
```

The original static viewer and eval-set editor are retained. The port never
calls `webbrowser.open`. Hand back the saved page or use only the configured
owned browser workflow. A server, if needed, must use the native background-job
API and loopback binding, with owned stop semantics. No `nohup` or shell detachment.
Read feedback only from its named artifact. Do not scan Downloads or invent user
approval. Without feedback, the human-review iteration remains incomplete.

Optional upstream packaging/format helpers are retained. They do not establish
behavior or justify metadata/prose tests. Run them only when the project permits
that validation and the packaging step applies. Native installation links the
complete directory; it does not require a .skill archive.
