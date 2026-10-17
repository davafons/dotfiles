# Workspace and simulator cleanup

Read [Playbook runtime](../references/playbook-runtime.md) before executing these steps.

Select each delegate's reasoning level and speed per [dav-mode's Subagents rules](../SKILL.md#subagents), using only controls the current harness actually supports.

## Runtime adaptation

This is the upstream worktree-cleanup method adapted to jj workspaces and the
native session APIs. Cleanup changes user state without a code review to catch
a mistake. Importing this playbook does not authorize any deletion.

The [read-only audit](../scripts/workspace-audit.py) requires jj 0.40+ and Python
3.9+. It fixes one operation for its observations, enumerates workspace paths
through jj, and never snapshots, fetches, changes bookmarks, or deletes state.
It reports captured change size, commit age, ancestry, conflicts, local/remote
bookmark refs, disk size, and optional live tracked-byte/mode differences.
Commit age is not last-use age. Unsnapshotted, untracked, ignored, and session
state can remain outside its captured view. Unknown is not clean or disposable.
PR state and chat usage stay unknown until checked through authorized evidence.
The helper never labels a row safe.

1. **Snapshot and audit.** Record `df -h /`, then run
   `python3 ~/.agents/skills/dav-mode/scripts/workspace-audit.py -b main --check-live-files <repo-path>`.
   Use the actual base bookmark when it is not `main`. Supply each known active
   or pinned workspace with `--active <name-or-exact-path>`. Save JSON outside
   the checkout. Run a slow audit as an owned background job through the native
   job API, not shell detachment. Paths come from jj, never a hand-written list.
   Read every field and its limits. Query each candidate's actual PR identity,
   state, and head through the forge, not a matching branch name alone. Read only
   named session metadata/transcript exports authorized for this task. No broad
   scan of Cursor, Yuke, Claude, or Codex histories. Do not fetch during this
   read-only audit; if fresher remote refs are needed, perform an authorized
   `jj git fetch` separately and rerun. Snapshot a candidate with `jj st` only
   after coordinating with its owner; the audit's live byte comparison does not
   itself snapshot it.
2. **The bucket is advice, not permission.** Obtain the actual pinned and active
   session set from the user or an authorized native API. Cross-check every
   candidate against that set. A pinned session can own sibling experiment and
   repro workspaces through children even when their names are absent from the
   sidebar. Primary and current workspaces stay held. Unknown usage stays held.
3. **Verify usage before deleting.** For every recent-chat row or doubtful
   candidate, use authorized read-only subagents to inspect its named transcripts
   and report pinned/ongoing usage and every workspace touched. Follow the native
   child lifecycle and desktop restrictions. Without authorized delegation or
   named transcript access, report that gate open; do not replace it with an age
   heuristic. Coordinate with all owners before treating a workspace as unused.
4. **Pause on irreversible loss.** jj captures ordinary tracked edits as commits,
   but the last snapshot does not prove the current disk is captured. Show the
   candidate's `jj diff --git`, captured changes, live differences, and untracked
   and ignored file inventory. Conflicts, unsaved editor buffers, recovery files,
   local databases, and retained test evidence count as state. Never classify an
   untracked or ignored file as scratch from its tracking status alone. Preserve
   valuable commits under owned recovery bookmarks and preserve approved disk
   state before forgetting a workspace. Get a decision for the concrete deletion
   set, including apparently empty and merged workspaces. This runtime's data-loss
   gate overrides upstream's automatic clean/merged deletion. In-use work pauses.
5. **Prune the confirmed set.** Recheck ownership, usage, and disk immediately
   before acting. Derive each exact path from a fresh jj workspace listing. With
   approval for that workspace, use `jj workspace forget <name>` to remove its
   registration; this does not remove the directory. Then remove only that
   verified directory under the same explicit approval. Never delete the primary
   repository, another owner's directory, a symlink target, or proof artifacts.
   Do not use Git worktree removal or pruning. Confirm `df -h /`, re-list jj
   workspaces, verify directory removal, and verify retained recovery bookmarks
   and evidence. Report failures instead of broadening a removal command.
6. **Simulators and other reclaimers.** Inventory the local simulator sets and
   runtimes before proposing reclaimers. The upstream candidates are XCTest
   testing clones, unavailable devices, old simulator runtimes, Xcode DerivedData
   and iOS DeviceSupport, editor snapshots/backups, and package caches. Inspect
   with `xcrun simctl --set testing list`, `xcrun simctl list devices unavailable`,
   and `xcrun simctl runtime list` when Xcode tools are available. For an explicitly
   approved testing set, `xcrun simctl --set testing delete all` removes its clones.
   `xcrun simctl delete unavailable` removes unavailable devices, and
   `xcrun simctl runtime delete <id>` removes a selected runtime. These are deletion
   operations, not diagnostics. Do not clear user editor state, package caches,
   devices, or runtimes without a concrete inventory and approval. Keep everything
   the user asked to retain. No GUI launch, audio, or clipboard work is implied.

**Reply:** `df -h /` before and after if deletion ran, space reclaimed, the exact
workspaces pruned, preserved state, and a one-line reason for each held candidate.
Name its owning session when known. If this was an audit only, say no deletion ran
and do not report reclaimed space. Name all unknown or unavailable evidence gates.
