# Pre-manifest profile references

These tests, the keymap, and the guides describe the retired factory-plugin profile. They remain as reference material for the deferred migration checks. Some tests import removed APIs or old source paths. They are not supported checks for the current installed Yuke.

Use [the manifest profile guard](../check-profile.py) for current types, startup, input dispatch, reload, disposal, and headless verification. The [current profile guide](../../README.md) describes the enabled plugins and verification limits.

Port a historical test to the current manifests and public declarations before treating its result as evidence. Keep each port focused on a behavior invariant. Do not restore the removed factory loader to make an old test run.
