# Refactor

1. Behaviour-preserving means the tests do not change. If a test must change,
   this is not a refactor.
2. Run whatever guards the code you are touching, and read the result rather
   than the fact that it ran.
3. One refactor at a time in hot code. Verify between them.
4. Unsure how far it reaches? **`/blast-radius`** before you land it, not
   after.
