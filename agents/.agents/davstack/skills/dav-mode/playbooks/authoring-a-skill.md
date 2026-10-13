# Authoring or modifying a skill

Read [Playbook runtime](../references/playbook-runtime.md) before executing these steps.

## Runtime adaptation

Use the installed [skill-creator](../../skill-creator/SKILL.md) as the native
runtime's general authoring dependency. It is the user-approved complete public
Anthropic workflow, not a claim that Cursor's unpublished built-in was recovered.
Follow its draft, paired-task evaluation, human review, iteration, and description
optimization loops. Its native adapter supplies bounded Yuke execution and
retained evidence. Reading or installing it is not proof that a full campaign ran.

For project verification skills, the installed
[create-verification-skill](../../create-verification-skill/SKILL.md) remains the
specialized generator. Improve an existing source rather than duplicate it.

Native project sources belong in `.agents/skills/<name>/`. Claude Code uses
`.claude/skills/<name>/`; prefer a link to the same source when both are needed.
Global development sources belong in dotfiles' davstack group and must be
explicitly registered in `bin/bin/agent-skills`. Inspect and improve an existing
source rather than create a competing skill. Use the native catalog and a real
mapped drive to prove discovery and behavior. Mechanical metadata/link checks
are validation, not behavior tests; respect the project's prohibition on tests
of skill prose, metadata, and reference structure. Subjective prose has no
synthetic test cases.

Use jj and `jj diff --git`, preserving unrelated working-copy changes. Step 4
uses [the native PR handoff](../references/playbook-runtime.md#pr-handoff).
Without publication authority, hand back the scoped verified diff instead.

**You own the skill's voice.**

1. Use the installed **skill-creator** workflow. This is the native mapping of the upstream Cursor **create-skill** dependency.
2. Validate the skill: frontmatter has `name` and `description`, referenced files exist, cross-skill links resolve.
3. Test cases if structural. Skip if subjective.
4. Run **Opening a PR**.

When in doubt, delete. Keep only prose that changes a decision. Tell it to do the thing and skip the reason. Explain only when the rule is confusing without one. Match tone to scope. Point at structural sources (types, READMEs, config) per the **encode-lessons-in-structure** principle skill. Delegate to other skills by path. Don't restate. A workflow you keep hitting but isn't captured → propose a new skill.

**Reply:** summary of the skill, key design decisions, validation notes.
