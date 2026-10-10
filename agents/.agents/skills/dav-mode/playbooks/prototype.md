# Prototype

**You own the decision, not the code.** The prototype is a throwaway instrument;
the real build is **Feature**. This is what "run it and let the result decide"
looks like in practice, and it is the one playbook where the
simplest-thing-that-works bar inverts: speed over polish, quality does not
matter, no tests. The rigor is in settling the decision cheaply.

1. Name the decision it exists to make. No decision means no prototype: this is
   a **Feature**.
2. Build it throwaway, outside the application source.
3. Comparing alternatives? Put them behind one switcher, each labelled, so the
   reader can name the one they want.
4. **Observe the thing you are deciding**: print the timing, log the output,
   screenshot the variant. The observation is the test here. There is no
   assertion to write.
5. Hand back the variants, the evidence, the tradeoffs and a recommendation.
   Say plainly that it is throwaway, and where it is.
