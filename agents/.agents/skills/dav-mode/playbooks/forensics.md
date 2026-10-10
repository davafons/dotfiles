# Forensics

The deliverable is a **diagnosis**, not a fix. Fixing is a **Bug fix** after.

1. Name the symptom as an observable: which metric, which log line, which user
   action. "It feels slow" is not one.
2. Read production before guessing.
3. **Check the thing everyone blames, and record that it was innocent.** The
   obvious culprit is where the day goes.
4. Say which of the five confidence steps in
   [blast-radius](../../blast-radius/SKILL.md) you reached. A diagnosis nobody
   proved is a hypothesis.
5. Hand back: the symptom, the cause, the evidence, and the cheapest check that
   would have caught it.
