---
name: interrogate
description: "Use for \"interrogate\", \"adversarial review\", \"multi-model review\", \"challenge this\", \"stress test this code\", \"find blind spots\", or \"tear this apart\". Multiple LLM reviewers challenge changes from independent angles."
disable-model-invocation: true
license: MIT
metadata:
  upstream: https://github.com/cursor/plugins/tree/1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def/pstack/skills/interrogate
  revision: 1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def
---

# Interrogate

## Runtime adaptation

Read the [shared working rules](../dav-mode/references/working-rules.md) and
[native coordination contract](../dav-mode/references/playbook-runtime.md#design-and-coordination).
They govern tools, model roles, workspace ownership, and authority throughout
this method. Preserve every phase and required output. Missing independent
workers, a judge, or safe output isolation leaves that gate open, not passed.
Installing this skill does not authorize delegation, model trials, or publication.

Spawn one reviewer per configured model to adversarially review code changes. The adversarial signal comes from model diversity, not assigned personas. The deliverable is a synthesized verdict. Do NOT auto-apply changes.

## Step 1, Scope

Identify what to review from context:

- If the user points at specific files or a diff, use that.
- For an owned jj change or stack, run `jj diff --git --from <owned-base> --to <owned-head>`. Resolve the exact scope first; do not include unrelated shared working-copy changes merely because they are above main.
- If the user's message references recent work, gather the relevant files.

Package the diff or file contents with any surrounding context files the reviewers need to understand the code.

## Step 2, Intent

Before spawning reviewers, state the intent in one clear paragraph from the user's message, commit messages, the PR description if one exists, and the code. If you're unsure about the intent, ask the user before proceeding.

## Step 3, Spawn Reviewers

Choose one fresh reviewer session per configured model under the native coordination contract, labeled Reviewer A, B, and so on. Use distinct models, not personas or reasoning levels of the same model. Existing `general` and `reviewer` roles may supply different models; verify engine receipts rather than assuming the role names prove it. Same-family models are allowed by this method, but do not claim different-family review or weaken a stronger caller gate.

Dispatch the authorized reviewers through supported native fan-out calls, then end the turn and wait for reports as required. Give every reviewer the same intent and complete template below, with an explicit read-only assignment. Yuke does not enforce a read-only sandbox for these roles. Do not auto-apply changes, including structural changes proposed by the code-quality lens.

A complete multi-model verdict needs at least two completed reviews from distinct models. If a required reviewer drops out, return only partial findings and name the gap. If a required distinct model or parallel dispatch is unavailable, report that gap and withhold the complete multi-model verdict. Do not silently replace a model, add a provider, open a PR, or present serial self-review as the missing reviewers.

Read `references/reviewer-prompt.md` and fill in the same template for every reviewer with the stated intent, the diff or file contents, the rubric from `references/rubric.md`, and the code-quality lens from `references/code-quality-review.md`.

## Step 4, Synthesize

As results come back, build a unified picture. Parse every reviewer's findings. Merge findings that describe the same issue differently, and note which models raised each one. Findings two or more models raised independently are the highest signal. Read a lone model's finding, but weight it accordingly. Note disagreements. If one model flags something and another explicitly says the opposite, that is context for the verdict.

## Step 5, Lead Judgment

You are the lead reviewer, a pragmatic senior engineer, not a neutral aggregator. Read `references/lead-judgment.md` for the full framework. Put every finding in one of four buckets, with the model(s) that raised it and a one-line rationale.

- **Act on**. Real issues affecting correctness, security, or maintainability given the actual goals. They would block a real PR.
- **Consider**. Legitimate, but you're not sure they outweigh the cost of addressing them now. Worth the user's attention.
- **Noted**. Technically valid but not actionable. Context-dependent, premature optimization, or low-impact at this stage.
- **Dismissed**. Wrong, nitpicky, or missing context, with a brief reason.

## Output Format

### Intent

> [The stated intent paragraph from Step 2]

### Reviewers

- Reviewer [label]: [model name], [N findings] (one bullet per reviewer)

### Act On

[Each: description, which models raised it, why it matters.]

### Consider

[Each: description, which models raised it, the tradeoff.]

### Noted

[Brief list.]

### Dismissed

[Each with a brief rationale.]

### Agreement Map

[Where models agreed and diverged, and what that pattern tells us.]
