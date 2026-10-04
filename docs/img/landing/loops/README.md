# Loops: one agentic scheme per class

Each clip and still is the real app on a sandbox camp built for the scheme (`capture/`).
orkcraft refuses a loop of roads, so loops close inside a building (Council rounds, the same orc)
or through you (Merge, Accept). The text for the site is in `loops.json`.

## peon — Red-Green: Code until the tests are green.

`Task → Barracks → Orc Council → Loot Vault`  
↩ `Forge: red tests → back to the same orc`

1. You move a task to In Progress. An orc picks it up.
2. Two reviewer agents check the patch until they agree.
3. Red tests send it back to the orc who wrote it.

**You:** You press Merge. **Limit:** 4 review rounds, $5 per batch.  
**Patterns:** Orchestrator–workers · Evaluator–optimizer · Sticky retry · Human gate · Budget cap

## knight — Night Watch: Production watches itself at night.

`Alert mail → Totem → Barracks → Forge → Catapult`  
↩ `Refund mail → Reply Mill → Loot Vault`

1. A Sentry alert comes in. An orc fixes the bug.
2. Tests pass, the fix merges, the release fires.
3. Refund mail gets a template reply. No model, $0.

**You:** You read the replies in the morning. **Limit:** Spend over $3 sounds the alarm.  
**Patterns:** Router · Prompt chain · Quality gate · No-model step · Budget alarm

## elf — Variants: Variants, critique, your pick.

`Brief → Barracks → Orc Council → Lake of Insight`  
↩ `Loot Vault: rejected → back to the same orc`

1. Drop a brief. Orcs draw variants in parallel.
2. Critic, Accessibility and Copy agents review until they agree.
3. Reject one and it goes back with your reason.

**You:** You pick the winner. **Limit:** 3 critique rounds, $1.  
**Patterns:** Parallel workers · Evaluator–optimizer · Feedback loop · Human gate

## lich — Daily Status: One morning digest, blockers flagged.

`Calendar + Board + GitHub → Catapult → team chat`  
↩ `Review stuck 2 days → Orc Council → unblock plan`

1. Calendar, board and GitHub feed one digest.
2. It goes out only when all three are in.
3. A review stuck for 2 days gets an unblock plan.

**You:** You read one message, not three tools. **Limit:** Too much in progress sounds the alarm.  
**Patterns:** Scheduled trigger · Fan-in · Router · Evaluator–optimizer · Threshold alarm

## How the clips are made

`capture/giflib.py` runs the real app on the camp (copied to a neutral `/srv/camp`), sends one or two
events and lets the chain run by itself, a frame every 0.1 s; one building opens at the end. Every frame
is checked for paths and ids before it is rendered. GIF at 1×, MP4 at 2×. In the sandbox the orcs and the
Council are simulated and the Catapult only dry-runs.
