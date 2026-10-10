# Visual parity

**You own pixel equivalence. The baseline is the spec and you do not touch it.**
For "make X match Y", a styling migration, or porting a surface. Equivalence is
verified by image diff, never by eye.

1. **Establish the baseline first**, before any change: screenshots of the
   current surface across its states, plus the target when matching two
   implementations. **No baseline, no parity claim.** This is a blocking
   prerequisite, not a follow-up.
2. **Anti-shortcut clauses, stated and held.** No editing the harness, no
   retaking the baseline, no restructuring the surface to make a diff pass. If
   the baseline itself looks wrong, stop and ask rather than edit it.
3. **One surface at a time.** Shared primitives go first, as a blocking phase.
4. **Verify each against its baseline by image diff.** A nonzero diff is a
   failure: investigate the pixels, do not wave it through.

**Reply:** what was migrated, the diff result for each, where the baseline
harness lives, and what is left.
