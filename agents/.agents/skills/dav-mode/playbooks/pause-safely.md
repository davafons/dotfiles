# Pause safely

**You own a clean stop. Leave a checkpoint a cold agent can resume from.** For
"I need to stop", going offline, or context about to compact. Explicit only:
"keep going" and "don't stop" mean continue.

1. **Stop at a safe boundary.** Finish the current atomic step or back out of
   it. Never stop mid-edit in a known-broken state. Start nothing new.
2. **Do not cross an irreversible line to pause.** No push, no deploy, no
   external message that was not already going out.
3. **Make the work durable where this repo keeps state**, not by inventing a new
   place for it.
4. Name the files you were editing, so the next agent can check them against
   whatever moved underneath.

**Reply:** where you are, what is on disk against what is only in your head, and
the first action on resume. This is a pause, not a final report. Resume is
[`session-pickup.md`](session-pickup.md) reading what you wrote.
