# Hillclimb

**You own the metric and the experiment's integrity.** For sustained improvement
of one measurable thing against a target. A one-off fix is **Bug fix** or
**Perf**; this is the loop.

The discipline is one change, one measurement, keep or revert. Never stack
untested changes, and never claim a win from reading the code.

1. **Pick the ruler before the target.** One metric, the direction that counts
   as better, and a workload that actually reproduces the complaint. If no case
   reproduces it, fix the repro instead of hillclimbing.
2. **Build the harness, prove it is sensitive, then freeze it.** Run cases you
   expect to differ and confirm the ruler separates them. Once frozen, one
   repeatable command emits the number, sampled past the noise (a median, not a
   single run). Changing the harness later invalidates every earlier number.
   Record the baseline, and a green run of whatever must keep passing.
3. **Write a stop predicate that pairs a target with a floor on attempts**, so a
   lucky first win cannot end the run. "At least 30% better and at least eight
   attempts" is the shape.
4. **Ground each hypothesis in a mechanism**, not a vibe. "Defer X off the boot
   path because it blocks first paint", never "try memoizing something".
5. **Loop.** One hypothesis, measure before and after on the frozen harness, run
   the guards. Accept only when the number moves past noise and the guards stay
   green; otherwise revert **in full**. A tweak that "might also help" does not
   ride along. Log every attempt, kept or reverted: that log is the run's memory
   and it stops the search circling.
6. **Push past the first plateau.** Several rejects in a row means pivot
   category, combine near-misses, or try something more radical. Correctness and
   simplicity outrank the number: revert a win that breaks behaviour, keep a
   simplification that holds it.
7. **Stop when the predicate is met**, or when the remaining ideas are honestly
   marginal. Do not relax the predicate to declare victory, and do not quit
   while cheap untried hypotheses remain.

**Reply:** the metric and target, baseline to final with the delta, attempts run
(kept against reverted), each accepted change on one line, and the best idea you
would try next.
