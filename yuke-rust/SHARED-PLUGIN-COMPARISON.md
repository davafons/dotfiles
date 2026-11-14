The personal Vim and agent-tools plugins are upstream `lostcoords/yuke-plugins` plus a personal delta. The comparison uses upstream main `39483ed`, which follows yuke `a3b9526`. Upstream still lacks that delta, so neither plugin can be replaced by a Git entry without feature loss. The profile's native host is `ca9a66a` on `davafons/rust-plugins`.

Upstream `39483ed` follows the API changes of yuke `a3b9526` (`inputSchema`, async `readDir`, flat session rows, `WrappedRow`, `onQuestion`). The personal copies carry the same renames.

| Vim capability | Upstream | Personal |
| --- | --- | --- |
| Composer motions, operators, registers, search, undo, repeat, Unicode handling | Yes | Same base |
| Composer mode service for other plugins | No | `mode`, `setMode`, `cancel`, `pending`, `onMode` |
| Transcript motions, visual selection, search, marks, source yanks | No | Yes |
| Shared registers between transcript and composer | No transcript support | Yes |
| Normal-mode Tab between transcript and composer | No | Yes |
| `gf` through the personal file-opening integration | No | Yes |

The register, text, and Unicode modules match upstream byte for byte. The composer adds the mode service in 28 lines. The entry point adds service registration, transcript binding, and Tab. `transcript.ts` and `service.ts` are personal. Upstream `04f776f` "feat(vim): add transcript navigation and composer mode service" exists only on the unmerged `davafons/vim-transcript` branch, which predates the current plugin API. Rebasing that branch onto upstream main and merging it would let the profile load upstream Vim as a Git plugin with a thin `gf` add-on.

Seven plugins read `composer-vim`: controls, dashboard, dollar-skills, path-completion, personal, prompt-history, and sudo-command.

| Subagent capability | Upstream | Personal |
| --- | --- | --- |
| Separate child context, background reports, follow-ups, stop, questions, read-only child UI | Yes | Same base |
| Saved model list and model picker | Yes | Same modules |
| Named roles with role prompts and model rules | No | general (gpt-6-luna, medium), dav-agent (parent model), reviewer (gpt-6.1-sol, xhigh) |
| Engine model receipt in spawn result | No | Yes |
| Explicit-user-request delegation policy | General upstream guidance | Personal prompt policy |
| Campaign quotas and tool restrictions | No | Enabled by `DAVSTACK_CAMPAIGN` |
| One parent view shared by parallel child runs | Yes | Yes |
| Tool names | spawn_subagent, message_subagent, stop | spawn_agent, send_agent_input, stop |

The list, model dialog, model settings, run log, and UI modules match upstream. The lifecycle differences are in the entry point, plus the personal `roles.ts` and `campaign.ts`. The personal tool names stay until the skills and campaign rules change in the same migration.

The local role implementation saves each child's role in `roles/<id>.json` and reads it back when a child of an earlier process opens, so the role prompt survives a restart. An unknown saved role falls back to general. `tools.test.ts` covers the read; a full restart in a real terminal is not tested.

## Upstream plugins that are not vim or subagents

| Plugin | Choice | Reason |
| --- | --- | --- |
| btw | Loaded as a Git plugin at `39483ed` | No personal equivalent. `/btw` and `/btw:history` work. Its own `Ctrl+K B` chord is shadowed, because controls takes `Ctrl+K` for focus-up and prompt history uses it too. Controls binds `Ctrl+X B` to `btw:ask` instead. |
| titles | Not loaded | Native sessions already have renameable titles from the first message, which sessions-reworked shows. Titles adds a model request per session and needs its own model setup. |
| mailbox | Not loaded | Adds model tools that push messages into other live sessions. That overlaps Herdr pane discovery and project-work messages, and widens what the model can do without a request from the user. |

## Check

```sh
mkdir -p /tmp/yuke-plugins-39483ed
git -C ~/workspace/yuke-rust-plugins-upstream archive 39483ed plugins | tar -x -C /tmp/yuke-plugins-39483ed
python3 ~/dotfiles/yuke-rust/scripts/compare_shared_plugins.py --upstream /tmp/yuke-plugins-39483ed
```

The script uses the real widget and session test hosts with scripted model replies. It makes no external model requests. It writes source hashes, a source diff, generated comparison tests, and logs under `~/workspace/yuke/target/shared-plugin-comparison`. The script reads an archive so it does not depend on the checkout's branch.

| Check | Result with the `ca9a66a` binary |
| --- | --- |
| Upstream Vim suite | 152 pass |
| Personal Vim suite | 158 pass |
| Upstream subagents suite | 55 pass |
| Personal service and role requirements | 2 pass |
| Same requirements with upstream packages | 2 expected failures |
| Personal transcript checks with upstream Vim | 6 expected failures |
| Upstream shared-parent-view check with personal subagents | 1 pass: both share one parent view |

The script checks each expected failure's count and diagnostic. Each one names behavior that upstream lacks. `tests/check-agent-tools.py` covers the personal roles, receipts, and stored settings over the real RPC wire instead.
