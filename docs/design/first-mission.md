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

1. **Play, don't ask.** Before the first quest: the class (one screen of chips) and the AI tools found (confirm with
   one press). Quiet hours and the look take their defaults, changed later in Settings. Industry and the typical day
   leave the first session.
2. **A first win within 3 minutes** of opening the town (a question answered), and free.
3. **A first real result within 5 minutes:** something useful about the person's own repository, read-only, its
   price said before it starts and under $0.05.
4. **Each quest teaches one control of the main scenario** (a cart on a road, ❓ and the console, parallel orks and
   🥩), never a settings screen.
5. **Nothing is faked as real.** A practice event is called a drill, on its card and in the Warchief's words.
6. **Skippable at every step.** A punk ork (today's path for those who orkestrate already) skips the mission for an
   empty town, as now.

## 3. Mission 1: Raise the camp — the person builds the first town

Reworked with the owner 2026-10-13. The person is **not given a town to work out**: they **build it, one building a
quest**, as a strategy game's first mission does ("Boss, we need a quality gate"). Each building is met by building
it, and shows what it is for at once. A quest log in the Warchief's line, one objective at a time; his lines may joke
(CLAUDE.md, the voice); what a quest spends is said plainly.

**So that building does not push the first win away:**

- **each quest raises one building, and it works at once:** the drill cart travels over what is built so far;
- **no looking for a place:** the Warchief lights a plot, one press raises the building there; it can be moved later;
- **each building, raised, says what it does in one line and asks one question at most**
  ([lighter-buildings.md](lighter-buildings.md) §3).

| quest | the Warchief | raised | what happens | time · cost |
|---|---|---|---|---|
| **1** | "Boss, the work needs somewhere to lie" | Task board | a drill card appears on it (a practice task, called a drill) | ≤ 1 min · free |
| **2** | "We need hands" | Agent pool, and the road from the board | a Grunt takes the card and asks a scripted question: ❓ on him, 🔥 on the pool; the person answers in the console | ≤ 3 min · free, no model: **the first win** |
| **3** | "Nothing leaves without a check" | Review gate, and its road | the drill's result reaches the gate; the person passes it and sees its waybill ([cart-waybill.md](cart-waybill.md)) | ≤ 5 min · free |
| **3½** | "Boss, in working hours the camp can look like an office" | — | the person presses the key and sees **the same town** in Office (the same carts and orks, as rows and numbers, calm and monochrome), then presses it again and is back in Camp. The Warchief: "By day the office, after work the camp. Switch when you like." A deed, *Two faces* | ≈ 15 s · free |
| **4** | "Listen to what goes on outside" | External listeners (GitHub) | **real work**, read-only: the person's unread issues and notifications sorted into cards; without `gh`, the repository's TODO and FIXME. The price said before it starts | ≤ 8 min · ≈ $0.02 |
| **5** (may be put off) | "Two at once" | — | two cards taken by two Grunts in parallel, each on its branch; 🥩 2/8; one asks; both reach the gate | ≤ 15 min · price said first |

**The class stays** (decided 2026-10-13): one screen, the class chosen from its chips. It changes the Warchief's words
and quest 4's source (a developer: GitHub; a manager: mail, through MCP, [connections.md](connections.md)); the
buildings and the order are the same for every class. Industry and the typical day leave the first session.

**Rewards:** a deed for each quest ([growth.md](growth.md)), the mascot's next stage when the mission ends.

**The hooks** (decided 2026-10-13, [open-questions.md](open-questions.md) Q16): asked once **before quest 4**, the first
real model call, showing line by line what is written into which AI tool's project settings, with how to take it back;
quest 5 needs the Warder on.

**Safety:** quests 1–3 run no model; quest 4 only reads; quest 5 works on branches, the Warder on, nothing merged
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
| open to quest 2 done (the first win) | ≤ 3 min (median of testers) |
| open to quest 4 done (real work) | ≤ 8 min |
| testers who finish quest 4 | ≥ 7 of 10 |
| testers who start quest 5 in the first session | ≥ 5 of 10 |

One question for every tester after the session, outside the mission: **do you need icons, illustrations or sprites
for what you build, and where do you get them today?** It tests whether asset making is worth advertising
([improve-buildings.md](improve-buildings.md) §12.4).

Quest 4 finished but no second session within a week means the first win was not worth coming back for: the quest's
job is changed, not the game around it.

## 6. Open

1. **Quest 4 for a person with no `gh` and no TODOs:** a short map of the repository as a Wiki page, or cards for its
   three largest files? To try with the first testers.
2. **Quest 1 on a machine with no AI tool yet:** the drill needs none; it may come before the tools are found, as the
   first thing seen.

## 7. Mission 2 and after: a second orkspace for a process that comes back (Later)

The owner, 2026-10-13: some time after Mission 1, a mission to set up a **second orkspace** for a process that repeats
**weekly or monthly**, for the person's class. It ties three things the docs left for later together:

- **orkspaces** stay hidden "until a person asks for a second town" ([cut-list.md](cut-list.md) §3): Mission 2 is
  how the second one comes;
- **recipes** (the Warchief laying a whole set: [ork-console.md](ork-console.md) §18) are what a mission builds;
- **the town's clock** ([town-time.md](town-time.md)) gets the scenario that teaches it.

**When:** after Mission 1 and a few days of use (the third to the seventh day), the Warchief offers the next mission in
the morning brief: a new chapter, not an improvement, so not in the 💡 list ([the-score.md](the-score.md)).

**What is built**, one orkspace (F2), by class:

| class | a process that comes back |
|---|---|
| a developer | a weekly sweep of dependencies and known vulnerabilities; release notes |
| a manager | a weekly report; a review of the quarter's goals by a product manager, a product designer and an AI architect (the owner's own case, [ork-console.md](ork-console.md) §18) |
| a new builder | sorting the week's playtest feedback; the week's batch of assets |

**It teaches:** a schedule on the clock's dial, the Review board and its clan, moving between orkspaces, the score.

**Spend said first:** the repeat's cost is named before it is turned on ("about 2 % of the window a week"); the carts
the town starts are marked ⏰ ([cart-waybill.md](cart-waybill.md) §2a).

**Later:** after the testers finish Mission 1. A mission is a file, so **missions from the community** stand beside
buildings from the community ([open-questions.md](open-questions.md) Q19).

## 8. The campaign: one concept a mission, up to a building of one's own (Later)

The owner, 2026-10-13: more missions, to bring in the harder ideas step by step, up to making a building of one's own.
The onboarding becomes a **campaign**: each mission brings **one new idea**, on the person's real work, built on the
ones before, as a strategy game brings a new kind of unit only when the player is ready.

| mission | the idea | what is built and done |
|---|---|---|
| 1. Raise the camp | carts, ❓, the gate | Task board, Agent pool, Review gate, External listeners (§3) |
| 1b. Proof before the gate | **a check inside the loop** | a building with a check last: the ork runs the tests (or the linter, or a schema) and reworks by itself until they pass; what reaches the person at the gate is already checked, and the waybill shows each round |
| 2. A process that comes back | time, a second orkspace | the class's repeating process (§7) |
| 3. The camp remembers | **a wiki the orks keep and read** | the Wiki gathers notes, decisions and code; the orks read less again, and the 🪵 per result falls ([the-score.md](the-score.md)) |
| 4. The chieftains' council | **agents that debate** | a Review board: several roles judge the person's document, each verdict down its exit |
| 5. Cheaper hands | **a script in an agent's place** | the Mason turns an agent's repeated step into a script; the score shows the 🪵 per result drop ([script-first.md](script-first.md)) |
| 5b. The town learns | **the outer loop: feedback, measured** | the person's 👎 with a note becomes a proposed change (a prompt, a rule, a tier); it is run on the building's cases against the old version on the Test bench; kept on probation only if the numbers say better ([improve-buildings.md](improve-buildings.md), `realm/evolution.py`). The Test bench comes off its freeze here, when its turn comes, not before |
| 5c. The camp at home | **what leaves the town goes through the gate** | mail answered by rules and one personal errand that comes back; every reply and registration waits at the Review gate until the person allows that road ([audience.md](audience.md) §4a) |
| 6. A building of one's own | **the building designer** | the Mason and the Alchemist build a building from the person's words; it can be shared |

**Why these two** (the owner's question, 2026-10-13: does the campaign cover the basics of loop engineering?). Taken
as designing the loops agents work in: an inner loop (a trigger, context, action, a check, a result) and an outer one
(measure, feedback, improve), with the person, the cost and the view of it all around them. Missions 1–6 covered the
trigger, the context, the tools and rights, many agents, the person in the loop, the cost and the view; two parts
were missing: **a check the ork must pass before a person sees the work** (1b), and **the outer loop that turns
feedback into a measured change** (5b). With them, the campaign walks the whole loop.

**A mission comes when its moment does**, the fixed order kept as a fallback: the orks reading the same files again
and again offers mission 3; long documents written by hand offer mission 4; results passed at the gate that later fail their tests offer 1b;
the person's 👎 piling up on one building offers 5b; the 💡 list finding an agent doing a
script's work offers mission 5. A mission then answers the person's real problem instead of reading as a lesson.

**Held to, as product:**

1. **Only Mission 1 is built now** (P0); the rest is the campaign's plan, **Later**.
2. **Missions are content, and content breaks when buildings change:** each mission is a data file, checked by the
   tests as the Test bench's scenarios are; else half of them break unseen within a month.
3. **A mission never unfreezes a feature:** the Wiki and the Review board are on the More shelf
   ([catalog-shelves.md](catalog-shelves.md)); missions 3 and 4 come when those buildings' turn does, not to bring it.
4. **Each mission:** one idea, fifteen minutes at most, real work on the person's own project, its cost said first, a
   deed at its end. A mission is a file, so the community can make them ([open-questions.md](open-questions.md) Q19).
