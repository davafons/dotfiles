---
name: blast-radius
description: Find what a change could break somewhere else before it ships, beyond the diff, and prove the one fact it is safe because of by running real code instead of writing it up. Use for "blast radius of X", "what could this break", or reviewing a small diff you do not trust.
metadata:
  origin: shirabe
  origin-path: docs/agents/blast-radius.md
  origin-revision: 968e24d69837e3efecca31487f7d8e8508e803c8
---

Read the [shared working rules](../dav-mode/references/working-rules.md) before applying this skill.
Project instructions supply the commands and conventions; examples are not prerequisites.

# Blast radius

Find what a change breaks somewhere else, before it ships.

Listing the callers is not the job. You can grep those in a second. The job is
the breakage grep will not show you.

## Do not trust your own writeup

A blast-radius writeup that sounds right is worthless. It reads as convincing
whether or not it is true, and that is the trap you are walking into. So do not
hand back the writeup. Find the one or two facts the whole thing depends on and
prove them by running code. Words are where you start, not what you ship.

### How sure are you

For each fact the change's safety depends on, get it as far down this list as is
cheap, and say where it stopped.

1. You said so. Worthless on its own.
2. You pointed at the line. A real `file:line`, or the library's own source.
3. You showed the bad case cannot happen. You walked the failure step by step
   and it does not reach.
4. You ran it. A script or test that calls the real code and fails loud if you
   are wrong.
5. You reproduced it in the running app.

Any safety fact you cannot get to step 4, say so out loud. Do not write it up as
settled.

## Steps

1. **Read the change.** The diff, the symbols it adds, changes and deletes, and
   what it now does differently, including the part the diff does not spell out.
2. **Find the one fact it is safe because of.** Most changes that look scary are
   safe because of a single fact ("this only drops already-dead cache entries").
   Find that fact. If it holds, most of the scary cases die at once. Spend your
   time here, not on a long list of maybes.
3. **Look where grep stops.** Read the source of the dependency you call, and check its
   pinned version. Work out when things run. Follow what a symbol search misses:
   the JSON an endpoint returns, a column, a cache key, a wire format, another
   language reading the same bytes, a feature flag, code three hops downstream.
4. **Be honest about each risk.** Give it a real chance of happening and a real
   cost if it does. Keep the risks you confirmed; list the ones you checked and
   cleared separately. Cite a real `file:line`. A search that finds nothing is
   still an answer. Never invent a caller or an API.
5. **Prove the one fact.** Write a script or test that runs the real code, run
   it, and paste what happened. If you cannot prove it cheaply, mark it
   unproven. Do not round up.

## What to hand back

- **What it does**, including the part that is not obvious.
- **The one fact it is safe because of.** State it, say which step you got it
  to, and show the proof. If you could not prove it, write unproven.
- **Risks.** Only the real ones. Each names how it breaks, the `file:line`, how
  likely and how bad, and how to check.
- **Cleared.** What you checked and why it is fine.
- **Before you land.** The cheapest test or repro that catches the real bug.

Write it through [unslop](../unslop/SKILL.md).
