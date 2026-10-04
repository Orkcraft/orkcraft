# Loops: one agentic scheme per class

Each picture is the real app on a sandbox camp built for the scheme: its buildings, its roads
(the event on each road is a real orkcraft event), and one cart sent down every road, caught
mid-road. Camp is on the ice biome; Office is the same map in grey frames.

orkcraft refuses a loop of roads (`scroll.subscribe`: "would close a loop of roads"), so every map
is a DAG. The loops close where orkcraft lets them: inside the Orc Council (objection → revision
→ another round, up to `max_rounds`), in the Barracks (a follow-up goes to the orc who did the
earlier part), through git (the Forge sees an updated branch) and through you (Merge, Accept).

## peon — Red-Green (`peon-red-green.png`)
Task Fields `tasks.status_changed` → Barracks `pool.done` → Orc Council `team.artifact_ready` → Loot Vault.
The Forge `forge.conflict` → Barracks (red tests go back to the same orc); The Forge `forge.merged` → Loot Vault.
Tally Crag `charts.threshold` → The Horn. Stops: Council 4 rounds / $2, Barracks $5, Halt All.

## knight — Night Watch (`knight-night-watch.png`)
Watchtower `mail.received` → Totem; Totem `totem.routed` (route `bug`) → Barracks `pool.done` → The Forge
`forge.merged` → The Catapult (POST to the deploy webhook); Totem (route `help`) → Reply Mill `mill.done` →
Loot Vault. Tally Crag `charts.threshold` → The Horn. Stops: Barracks $5, spend warn $1.50 / cap $3.

## elf — Variants (`elf-variants.png`)
The Pit `pit.text` (the brief) → Barracks (three orcs) `pool.done` → Orc Council `team.artifact_ready` →
Lake of Insight. Loot Vault `generator.rejected` → Barracks (send back); Loot Vault `generator.accepted`
→ Token Mill (tokens JSON → CSS, no model). Stops: Council 3 rounds / $1, Barracks $3, your Accept.

## lich — Daily Status (`lich-daily-status.png`)
War Drum `calendar.day_schedule`, Sprint Board `tasks.status_changed`, Watchtower `watch.cron` → Digest
Catapult (fan-in, `wait_for` all three) `catapult.sent` → Loot Vault. Watchtower `watch.github` → Totem
(route `stuck`) → Orc Council (an unblock plan). Tally Crag (tasks per column) `charts.threshold` → The Horn.

## How

```bash
python capture/seed_loop_peon.py work/peon && python capture/shoot_loop_peon.py work/peon .
```
(the scripts sit next to `docs/img/landing/buildings/capture/` and import its `classes.py`,
`shootlib.py` and `shotlib.py`).

## Animations (`<class>.gif`, `<class>.mp4`, 5 s)

`capture/giflib.py` runs the real app on the scheme's camp (copied to a neutral `/srv/camp`, so
no hut can show a path of this machine) and takes a frame every 0.1 s of real time: one or two
events are sent, the buildings take the carts and change their status, the chain goes on by
itself (the sandbox's simulated orcs work 1.6 s; the Council's simulated members agree), and one
building opens at the end. Every frame is checked for paths, session ids and addresses before
it is rendered. GIF at 1×, MP4 at 2×, the last frame held for 0.8 s.

The flow of each clip, second by second, and the agentic patterns it shows are in `loops.json`.
