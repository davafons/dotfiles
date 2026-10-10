# Bug fix

1. Reproduce it. A bug you cannot reproduce is a bug you cannot fix.
2. Find the cause, not the symptom. Read the surrounding code first.
3. Write the failing test **and watch it fail** (**`/tdd`**, which also says what
   to do when a cheap test path does not exist).
4. Fix it. Watch the test pass.
5. Ask what class this belongs to, and whether a lever catches the rest. See
   **Encode**.
6. User-visible? Write the changelog note in the same change.
