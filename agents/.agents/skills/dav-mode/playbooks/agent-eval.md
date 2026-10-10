# Agent eval

**You own the experiment design: plan, blind, run, synthesise.** For measuring
whether a change to a prompt, a rule or a playbook actually changes how an agent
behaves, before promoting it.

The failure mode is the observer effect. **An agent that knows it is being
evaluated behaves differently**, so candidates run blind.

**Non-negotiables for blinding:**

- No `eval`, `test`, `judge`, `rubric`, `score`, `compare`, `benchmark` or
  `candidate` in any directory, file or prompt the candidate sees.
- The prompt reads like an organic request. State the goal, not the meta: "build
  me a small importer", never "show me how you follow the rules".
- **No chain-eliciting cues.** Do not ask a candidate which rules it applied;
  that inflates citation behaviour. Grade from the shape of the work, not from
  self-report.
- Sanitise directory names. Project-shaped names, not `candidate-1`.
- Do not tell a candidate that other candidates exist.
- The judge may know it is judging, but sees outputs by sanitised label only.
- Comparing two variants: **one judge, one pass, one scale.** Two judge runs
  with different prompts do not compare, the calibration drifts.

**Steps:**

1. **Frame.** What variant is under test, and what counts as success. Write the
   rubric (three to six concrete criteria) for the judge only.
2. **Set up sanitised environments**, one per candidate, with the variant in
   place and whatever context an organic task would have.
3. **Author one organic prompt.** What a person would actually type.
4. **Run the candidates**, same prompt to each. Use delegated or parallel
   agents only when the user explicitly requested them; otherwise use authorised
   serial runs. Report unavailable independent runs as a gap, not a simulated eval.
5. **Run one judge**, blind to which output came from where.
6. **Verify from what they did, not what they said.** Which files a candidate
   actually opened is evidence; citing a rule is not reading it, and reading it
   is not applying it.
7. **Read every output yourself** and compare against the judge. Disagreement
   means a biased model or an ambiguous rubric.

**Reply:** the variant, the rubric, per-candidate notes, the judge's verdict,
your synthesis, and whether to promote.
