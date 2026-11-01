import { assert, equal, test, throws } from "yuke:test";
import { promptFor } from "../.config/yuke-rust/plugins/peek/prompt.ts";

test("the observer drops older exchanges to bound the encoded request while preserving its frozen evidence", () => {
  const snapshot = { evidence: "x".repeat(110_000), capturedAt: "fixture" };
  const exchanges = [
    { question: "older", answer: "🌟".repeat(2000) },
    { question: "newer", answer: "🌟".repeat(2000) },
  ];
  const prompt = promptFor(snapshot, exchanges, "What changed?");
  assert(new TextEncoder().encode(prompt).length <= 120 * 1024);
  equal(JSON.parse(prompt), { snapshot, conversation: [exchanges[1]], question: "What changed?" });
  equal(exchanges.length, 2);
});

test("an oversized encoded snapshot cannot reach the observer model", () => {
  throws(() => promptFor({ text: '\\"'.repeat(70_000) }, [], "Explain."));
});
