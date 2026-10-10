# Unfinished loop plugin

This directory preserves the loop source added during the profile migration. The entry still uses the retired factory-plugin API. It is not in `config.json` and does not run in the active profile.

The scheduler core has a standalone check:

```sh
bun test yuke/experimental/loop/loop-core.test.ts
```

A later port must use a manifest entry and the current engine event contract. Verify cancellation, reload cleanup, queued-input ownership, and explicit scheduling authorization before enabling it. The core test alone does not prove native integration.
