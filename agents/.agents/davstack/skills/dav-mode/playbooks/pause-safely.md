# Pause safely

Read [Playbook runtime](../references/playbook-runtime.md) before executing these steps.

**You own a clean stop. Leave a checkpoint a cold-start agent can resume from.** This is explicit only. On "keep going", "going to bed, keep going", or "don't stop", do not pause.

1. Stop at a safe boundary. Finish the current atomic step or back out of it. Start nothing new, and cancel any nested subagents.
2. Take no irreversible action to pause. No PR and no push unless you already had one out.
3. Make the work durable through the repository's native change model. In jj, the working copy is already a change; preserve it and save the project's checkpoint. In Git-only repositories, make a scoped `wip:` commit when needed. Do not bundle other workers' changes. If the tree is broken, record that explicitly in the checkpoint and any WIP description.
4. Write the resume note outside the chat context using the project's checkpoint store, or a resume file such as `/tmp/<slug>-resume.md` when no store exists. Capture intent, what you were doing, progress and what's verified, current state, next steps, key files, and gotchas. If a decision trail exists, point at it instead of duplicating it.

**Reply:** where you are in the loop, what's on disk versus still in your head (paths, no diff dumps), the native change IDs and durable working-copy state, and the first action on resume. This is a pause, not a final report.
