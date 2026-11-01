The current upstream Vim and subagents packages cannot replace the personal versions without feature loss. Most of their code is already shared. The remaining differences fit focused upstream contributions.

This comparison uses `lostcoords/yuke-plugins` at `a315f66a9a19498648f5977dac7b37f35d986d75` and the canonical Rust profile in this directory. Native upstream is `224f915`. The installed personal native source is `9a0c993`.

| Vim capability | Upstream | Personal |
| --- | --- | --- |
| Composer motions, operators, registers, search, undo, repeat, Unicode handling | Yes | Same base |
| Composer mode service for other plugins | No | `mode`, `setMode`, `cancel`, `pending`, `onMode` |
| Transcript motions, visual selection, search, marks, source yanks | No | Yes |
| Shared registers between transcript and composer | No transcript support | Yes |
| Normal-mode Tab between transcript and composer | No | Yes |
| `gf` through the personal file-opening integration | No | Yes |

The register, text, and Unicode modules match byte for byte. Composer changes add the mode service. The entry point adds service registration and transcript binding. All six additional personal Vim tests cover transcript behavior.

Seven plugins read `composer-vim`: controls, dashboard, dollar-skills, path-completion, personal, prompt-history, and sudo-command. The dashboard also sets Normal mode for an empty chat. Both composer implementations otherwise start in Insert mode. The personal Vim README contains stale claims about startup mode and a blocked transcript port.

The Vim contribution can use two changes. First, expose and document the composer service. Second, add transcript navigation after the native source-mapping correction lands. The current personal transcript module imports a file-reference parser outside its package and calls `personal-navigation`. Move file opening into a separate integration. Keep the upstream Vim package independent of personal services. Do not copy the current folder unchanged.

Native upstream still lacks the `elision` source mapping used by the transcript tests. The personal native branch has that correction. Transcript verification must cover clipped tool headings, folds, and reflow before release.

| Subagent capability | Upstream | Personal |
| --- | --- | --- |
| Separate child context, background reports, follow-ups, stop, questions, read-only child UI | Yes | Same base |
| Saved model list and model picker | Yes | Same modules |
| Named roles with role prompts and model rules | No | general, dav-agent, reviewer |
| Engine model receipt in spawn result | No | Yes |
| Explicit-user-request delegation policy | General upstream guidance | Personal prompt policy |
| Campaign quotas and tool restrictions | No | Enabled by `DAVSTACK_CAMPAIGN` |
| One parent view shared by parallel child runs | Yes | No |
| Tool names | spawn_subagent, message_subagent, stop | spawn_agent, send_agent_input, stop |

The list, model dialog, model settings, run log, and UI modules match byte for byte. The lifecycle differences are concentrated in the entry point. Upstream already has the cancellation-report correction previously ported into the personal version.

Contribute generic role configuration, role restoration, and model receipts to upstream subagents. Keep personal role text, model IDs, delegation policy, and campaign rules in the profile. A review role is a prompt assignment, not a sandbox. Adopt upstream tool names in personal skills and campaign rules in the same migration. Preserve model preferences and role metadata when the plugin data directory changes from `agent-tools` to `subagents`.

The local role implementation also needs a cold-restart check. It writes role files but never reads them. Its in-memory role map therefore cannot restore the role prompt in a fresh process. This is a source finding, not a completed restart test.

The repeatable check is:

```sh
python3 ~/dotfiles/yuke-rust/scripts/compare_shared_plugins.py
```

The script uses the real widget and session test hosts with scripted model replies. It makes no external model requests. It writes source hashes, a source diff, generated comparison tests, and logs under `~/workspace/yuke/target/shared-plugin-comparison`.

| Check | Result |
| --- | --- |
| Upstream Vim suite | 117 pass |
| Personal Vim suite | 123 pass |
| Upstream subagents suite | 53 pass |
| Personal service and role requirements | 2 pass |
| Same requirements with upstream packages | 2 expected failures |
| Personal transcript checks with upstream Vim | 6 expected failures |
| Upstream shared-parent-view check with personal subagents | 1 expected failure: two parent views instead of one |

Expected failures demonstrate missing behavior. They are not upstream suite regressions. The script checks both the failure count and its diagnostic. The shared-parent-view test counts real session opens. It does not measure a timing speedup.

Keep both personal plugins installed until these gaps close. No installed configuration or plugin source changes form part of this comparison.
