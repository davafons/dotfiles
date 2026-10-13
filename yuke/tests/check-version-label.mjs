#!/usr/bin/env node
import assert from "node:assert/strict";
import { versionLabel } from "../.config/yuke/plugins/build-status/version-label.js";

const cases = [
  ["0.0.1-dev+e43023f2c5a7.b20261012130844", "0.0.1-dev+e43023f2"],
  ["0.0.1-dev+8924217fd30a.b20261013010637", "0.0.1-dev+8924217f"],
  ["0.0.1-dev+abcdef123456.dirty.b20261012130844", "0.0.1-dev+abcdef12.dirty"],
  ["0.0.1-dev+abcdef123456", "0.0.1-dev+abcdef12"],
  ["0.0.1-dev+abcdef12.dirty", "0.0.1-dev+abcdef12.dirty"],
  ["0.0.1-dev+abc123.b20261012130844", "0.0.1-dev+abc123"],
  ["0.0.1-dev+source.b20261012130844", "0.0.1-dev+source"],
  ["0.0.1-nightly.20261012+d74a069", "0.0.1-nightly.20261012+d74a069"],
  ["0.0.1-dev", "0.0.1-dev"],
  ["1.2.3", "1.2.3"],
  ["1.2.3+vendor.metadata", "1.2.3+vendor.metadata"],
  ["1.2.3+abcdef123456.vendor", "1.2.3+abcdef123456.vendor"],
];
for (const [version, expected] of cases) {
  assert.equal(versionLabel(version), expected, version);
  assert.equal(versionLabel(versionLabel(version)), expected, "Formatting twice must preserve the label");
}
console.log("PASS: compact UI labels preserve releases, prereleases, short revisions, dirty markers, and other metadata");
