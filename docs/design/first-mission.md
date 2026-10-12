# Design — the first session is a game's first mission

Status: proposal 2026-10-12, the owner's ask; nothing built. Priority **P0**: it is the first fifteen minutes.
Builds on [gui-onboarding.md](gui-onboarding.md) and [onboarding.md](onboarding.md) (today's steps),
[growth.md](growth.md) (deeds, the mascot), [ork-console.md](ork-console.md) (❓, the console, the one status),
[cut-list.md](cut-list.md) (the onboarding row), [dogfood-logs.md](dogfood-logs.md) (the events).

## 1. Why

Today a new person answers a form first: how well they know agent orkestration, role, industry, a typical day as
chips, their AI tools, what the first town should do, the camp rules. Three to seven steps before one ork works.

The owner's ask: **the first session should feel like a game more than like automating a process, and give a first
success as fast as possible.** A strategy game's first mission does both: few words, one objective at a time, a win
in minutes, and by its end you know the controls.

## 2. The rules

1. **Play, don't ask.** Before the first quest, only what cannot be guessed: the AI tools found (confirm with one
   press). Quiet hours and the look take their defaults, changed later in Settings. Role, industry and the typical
   day leave the first session.
2. **A first win within 90 seconds** of opening the town, and free.
3. **A first real result within 5 minutes:** something useful about the person's own repository, read-only, its
   price said before it starts and under $0.05.
4. **Each quest teaches one control of the main scenario** (a cart on a road, ❓ and the console, parallel orks and
   🥩), never a settings screen.
5. **Nothing is faked as real.** A practice event is called a drill, on its card and in the Warchief's words.
6. **Skippable at every step.** A punk ork (today's path for those who orkestrate already) skips the mission for an
   empty town, as now.

## 3. Mission 1: Raise the camp

A quest log in the Warchief's line, one objective at a time, as a strategy game shows its quests. The Warchief's
lines may joke (CLAUDE.md, the voice); what a quest spends is said plainly.

| quest | what happens | teaches | time · cost |
|---|---|---|---|
| **1. The first cart** (a drill) | a practice issue comes in through External listeners, rolls along the road to the Task board, then to the Agent pool. Its Grunt asks a scripted question ("bug or feature?"): ❓ on the Grunt, 🔥 on the pool. The person answers in the console; the fire goes out, the card is done | a road and its cart; ❓, the console, answering | ≤ 90 s · free, no model |
| **2. Real work** | one Grunt does one real, read-only job on the person's repository: with `gh`, **the unread** (open issues and notifications) sorted into Task board cards, each with a line on what it is; without `gh`, the repository's TODO and FIXME made into cards. The price shown before it starts | that the town works on *their* project | ≤ 5 min · ≈ $0.02, light tier |
| **3. Two at once** (may be put off: "Later") | the person picks two cards; two Grunts take them in parallel, each on its own branch; 🥩 2/8; one asks, the person answers; both diffs reach the Review gate; the person passes one | the main scenario: who works, who waits, stepping in | ≤ 10 min · price shown before it starts |

**Rewards:** a deed for each quest ([growth.md](growth.md): beside today's First town and First road), the mascot's
next stage when the mission ends, and the Warchief's line saying what was learned. Mission 1 done is the moment the
testers' fifteen minutes are measured to.

**Safety:** quest 1 runs no model; quest 2 only reads; quest 3 works on branches, with the Warder on and nothing merged
without the person.

## 4. What it changes

- **The onboarding form** shrinks to the AI tools found; the rest of it goes to Settings or out. [cut-list.md](cut-list.md)
  said "measure first"; this decides it.
- **The demo** (`orkcraft --demo`) stays a sandbox to look at; the mission is played in the person's own town.
- **The first deeds** of [growth.md](growth.md) are earned in the mission, not left to be found.
- **README:** "Try it in a minute" ends on the mission, not on an empty town.

## 5. How we know

To the local event log and, as buckets, to the usage stats ([dogfood-logs.md](dogfood-logs.md) §3): `quest_started`,
`quest_done`, `quest_skipped`, each with its seconds.

| measure | aim |
|---|---|
| open to quest 1 done | ≤ 90 s (median of testers) |
| open to quest 2 done | ≤ 5 min |
| testers who finish quest 2 | ≥ 7 of 10 |
| testers who start quest 3 in the first session | ≥ 5 of 10 |

One question for every tester after the session, outside the mission: **do you need icons, illustrations or sprites
for what you build, and where do you get them today?** It tests whether asset making is worth advertising
([improve-buildings.md](improve-buildings.md) §12.4).

Quest 2 finished but no second session within a week means the first win was not worth coming back for: the quest's
job is changed, not the game around it.

## 6. Open

1. **Quest 2 for a person with no `gh` and no TODOs:** a short map of the repository as a Wiki page, or cards for its
   three largest files? To try with the first testers.
2. **Quest 1 on a machine with no AI tool yet:** the drill needs none; it may come before the tools are found, as the
   first thing seen.
