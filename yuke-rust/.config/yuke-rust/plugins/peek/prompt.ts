/** Encode a frozen observer request. Drop older exchanges to fit 120 KiB. An oversized snapshot throws before a request. */
export function promptFor(
  snapshot: unknown,
  exchanges: readonly { question: string; answer: string }[],
  question: string,
): string {
  const recent = exchanges.slice(-2);
  const encoder = new TextEncoder();
  let prompt = JSON.stringify({ snapshot, conversation: recent, question });
  while (encoder.encode(prompt).length > 120 * 1024 && recent.length > 0) {
    recent.shift();
    prompt = JSON.stringify({ snapshot, conversation: recent, question });
  }
  if (encoder.encode(prompt).length > 120 * 1024)
    throw new Error("The captured snapshot exceeds the observer request limit.");
  return prompt;
}
