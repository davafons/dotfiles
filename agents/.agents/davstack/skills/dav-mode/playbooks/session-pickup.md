# Session pickup

Read [Playbook runtime](../references/playbook-runtime.md) before executing these steps.

**You own the resume point. Read the prior trail, don't redo it.**

1. Locate the prior trail. The named session's history through the current harness's authorized API or export, the project's checkpoint, an agent-run URL, or a pushed branch. Do not assume another editor's transcript paths or search unrelated sessions. Read the metadata overview and last messages first, then scan back for the decision points. Parse a long transcript in a subagent and keep the reduced timeline in the main thread (the [guard-the-context-window principle](https://github.com/cursor/plugins/blob/1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def/pstack/skills/principle-guard-the-context-window/SKILL.md)).
2. Reconstruct operational state. The branch and worktree, what already landed (native history and diff against the base; in jj use `jj log` and `jj diff --git --from <base>`), the open todos, the decisions made. The prior trail is authoritative input. Resist the bias to re-derive it.
3. Diff done vs pending. Compare what shipped against what was planned, name the resume point, do not re-run the prior repro or redo completed work. A "let me verify from scratch" pass means you're treating the trail as untrustworthy when it's authoritative.
4. Route the remaining work to the matching playbook and pick the verdict: continue the execution, ship a finished recommendation, ratify or override a prior conclusion, or postmortem a failed run. The pickup playbook ends here. The routed playbook owns the rest.
5. Verify the inherited claims against the original goal on the real artifact (the [prove-it-works principle](https://github.com/cursor/plugins/blob/1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def/pstack/skills/principle-prove-it-works/SKILL.md)). A passing prior self-report is not the proof.

**Reply:** where the prior agent stopped, what you inherited vs redid (ideally nothing redone), the resume point, and the outcome.
