# Session pickup

**You own the resume point. Read the prior trail, do not redo it.** For "take
over this", "continue where the other agent left off", or arriving at a working
copy someone else was mid-way through.

A pickup is inheritance. The prior agent already paid for reading the code,
running the repro and making the choices. Re-deriving loses the bias check and
burns the context twice.

1. **Find the trail.** The plan that owns the work, and what is actually on
   disk right now.
2. **Reconstruct state, do not rebuild it.** What landed, what is half-done,
   which files are being edited by somebody else right now (check mtimes).
3. **Diff done against pending.** Name the resume point. Do not re-run the prior
   repro. **"Let me just verify it all from scratch" is the tell** that you are
   treating an authoritative trail as untrustworthy.
4. **Route the rest** to the playbook that matches it. Pickup ends here.
5. Verify the inherited _claims_ against the goal on the real artifact. A prior
   self-report is not proof, and this is the one thing worth re-running.

**Reply:** where the prior agent stopped, what you inherited against what you
redid (ideally nothing), the resume point, and the outcome.
