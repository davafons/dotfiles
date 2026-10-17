# Incident & Postmortem Context

Read [the native runtime contract](../../../dav-mode/references/playbook-runtime.md). Vendor tools below are source examples, not assumed services or permission to configure them. Use only available, authorized, read-only evidence tools.

- **Linear**: look for tickets labeled `incident`, `sev-*`, `postmortem-action-item`, `reliability`
- **Slack**: search `#sev-*` and `#incident-*` channels around the dates the target code was added
- **Git**: commits with messages like "fix for incident", "add defensive check", "revert" followed by "re-apply with..." are strong signals
