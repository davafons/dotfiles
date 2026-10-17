# Trace forensics

Read [Playbook runtime](../references/playbook-runtime.md) before executing these steps.

Select each delegate's reasoning level and speed per [dav-mode's Subagents rules](../SKILL.md#subagents), using only controls the current harness actually supports.

**You own the diagnosis from the artifact.**

Distinct from **Runtime forensics**, which instruments the live process. Here the capture already exists. The artifact is a fixed dataset, read it, don't re-run it. Use this computer's proven CLI, API, or computer-use workflow. A cloud worker is not required. Apply desktop permissions before opening a native GUI. Use jj for source history. Keep tooling generic: a DevTools or trace parser for cpuprofile and `.json.gz`, a text editor for a spindump, your heap tooling for a heapsnapshot.

1. Identify the format and load it with the right tool. Parse large artifacts through an authorized native subagent when available (the [guard-the-context-window principle](../../principle-guard-the-context-window/SKILL.md)) and keep the reduced finding in the main thread. Without delegation permission, use bounded queries directly and report that no independent parser ran.
2. Transform the raw artifact into a form you can query. Dump the trace or heap snapshot into sqlite, one row per sample, frame, or node. Reach the queryable shape before you read.
3. Narrow to the cause. Query for the frames that hold the most time and walk the call tree to the hot path. For a leak, follow the retainer chain from the leaked object to a GC root. For a spindump, find the thread stuck on-CPU or blocked and its wait reason.
4. Attribute to source. Map the hot frame to file, symbol, and line via the artifact's own symbols. A frame with no source mapping is not yet a diagnosis. Resolve the symbols, or say plainly the artifact does not carry them.
5. If you have a paired capture, diff the before and after artifacts to confirm. Otherwise, mark the finding as the strongest hypothesis the artifact supports, not a confirmed cause.
6. Hand back a cited diagnosis, no fix unless asked. Route to Bug fix or Perf issue once the cause is known. Throughput checkpoint stays one line: `throughput checkpoint: n/a, read-only forensics`.

**Reply:** the artifact and format, the reduced finding, the source location, the artifact paths, and whether a paired capture confirmed it.
