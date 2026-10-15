# Design — the first session is a game's first mission

Status: proposal 2026-10-12, the owner's ask. Priority **P0**: it is the first fifteen minutes. **Built 2026-10-14
(B7): quests 1 to 3½** (`realm/mission.py` the quests and their words, `core/mission.py` the work, `gui/mission.py`
and `js/mission.js` the quest log in the Workchief's line); offered first on the onboarding's town step ("Set up the
camp myself"). The drill runs no model: the Agent pool runs it by a script while its `drill.json` is there.
**Quests 4 and 5 and the hooks, 2026-10-14 (B8):** before quest 4 the hooks are asked for once, file by file what is
written (`hooks/install.py` `preview`), how to take them back (`orkline hooks remove`, Settings → Security reviewer)
and that they never block a tool when Orkline fails. Quest 4 reads only, **free, no model** (`realm/mission_work.py`:
the person's GitHub notifications and issues of this repository through `gh`, else the tracked TODO and FIXME lines,
sorted by rules, not a model: the ≈ $0.02 sort below is not built); the cards wait on the board (`send_new` off).
Quest 5 needs the hooks; its price is said first: two runs on the main tool, on branches, no new run once the pool
spent $2.00 more (its `budget_usd`, taken off when the quest ends); both results wait at the Review gate. Not yet:
"one asks" in quest 5 (a real ork asks only when it needs to), the deeds and the mascot's stage, the class's words.
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
5. **Nothing is faked as real.** A practice event is called a drill, on its card and in the Workchief's words.
6. **Skippable at every step.** A punk ork (today's path for those who orkestrate already) skips the mission for an
   empty town, as now.

## 3. Mission 1: Raise the camp — the person builds the first town

Reworked with the owner 2026-10-13. The person is **not given a town to work out**: they **build it, one building a
quest**, as a strategy game's first mission does ("Boss, we need a quality gate"). Each building is met by building
it, and shows what it is for at once. A quest log in the Workchief's line, one objective at a time; his lines may joke
(CLAUDE.md, the voice); what a quest spends is said plainly.

**So that building does not push the first win away:**

- **each quest raises one building, and it works at once:** the drill cart travels over what is built so far;
- **no looking for a place:** the Workchief lights a plot, one press raises the building there; it can be moved later;
- **each building, raised, says what it does in one line and asks one question at most**
  ([lighter-buildings.md](lighter-buildings.md) §3).

| quest | the Workchief | raised | what happens | time · cost |
|---|---|---|---|---|
| **1** | "Boss, the work needs somewhere to lie" | Task board | a drill card appears on it (a practice task, called a drill) | ≤ 1 min · free |
| **2** | "We need hands" | Agent pool, and the road from the board | a Grunt takes the card and asks a scripted question: ❓ on him, 🔥 on the pool; the person answers in the console | ≤ 3 min · free, no model: **the first win** |
| **3** | "Nothing leaves without a check" | Review gate, and its road | the drill's result reaches the gate; the person passes it and sees its waybill ([cart-waybill.md](cart-waybill.md)) | ≤ 5 min · free |
| **3½** | "Boss, in working hours the camp can look like an office" | — | the person presses the key and sees **the same town** in Office (the same carts and orks, as rows and numbers, calm and monochrome), then presses it again and is back in Camp. The Workchief: "By day the office, after work the camp. Switch when you like." A deed, *Two faces* | ≈ 15 s · free |
| **4** | "Listen to what goes on outside" | External listeners (GitHub) | **real work**, read-only: the person's unread issues and notifications sorted into cards; without `gh`, the repository's TODO and FIXME. The price said before it starts | ≤ 8 min · ≈ $0.02 |
| **5** (may be put off) | "Two at once" | — | two cards taken by two Grunts in parallel, each on its branch; 🥩 2/8; one asks; both reach the gate | ≤ 15 min · price said first |

**The class stays** (decided 2026-10-13): one screen, the class chosen from its chips. It changes the Workchief's words
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
- **recipes** (the Workchief laying a whole set: [ork-console.md](ork-console.md) §18) are what a mission builds;
- **the town's clock** ([town-time.md](town-time.md)) gets the scenario that teaches it.

**When:** after Mission 1 and a few days of use (the third to the seventh day), the Workchief offers the next mission in
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

## 9. Mission 1 on v3's camp, and the campaign's next (the owner, 2026-10-14, evening)

1. **The quests meet the stations** ([v3-prompts.md](v3-prompts.md) §13): quest 1 raises the dispatcher's booth and the
   drill cart stands on its siding; quest 3's "pass" is **lifting the Review gate's barrier**.
2. **A finale after quest 3, no new quest:** the passed drill cart rolls on to the catapult and is launched, its cost
   flying above it ([the-score.md](the-score.md)); marked a drill, nothing leaves the town. It is the GIF's frame.
3. **Rewards on v3's scheme** (v3-prompts §14): a deed per quest; at the mission's end the portrait's stage 2 and the
   first item, "the first cart" on a plinth, in the inventory.
4. **The campaign's next mission is 1b, Proof before the gate** (a check inside the loop): the most useful to a
   developer, and it raises the quality the score guards. Then Mission 2, a process that comes back.
Built with I1 (items 1–3); 1b after the inventory.

**Built 2026-10-14 (M1), items 1–3.** Quest 1's Task board stands as the dispatcher's booth with the drill cart on its
siding (Camp v3 draws it from the board's To Do). Quest 3's press, once the drill waits on the weighbridge with the
barrier down, is **Lift the barrier** (`mission.raise` on quest 3, `core/mission.py` `_lift`): the person's pass. The
drill goes on no road and teaches the pool nothing, so nothing leaves the town even when the gate has a road out.
**The finale** (`finale` in the quest log's snapshot for 14 s, `js/camp/carts.js` `Finale`): the drill rolls off the
weighbridge along the line, "Drill · free" above it; the Publisher launches it if the town has one, else it leaves at
the line's buffer stop; the view follows the gate, then the drill. **Rewards** (`realm/growth.py`): a deed per quest
(`quest.<id>`, listed only once earned); **Mission 1 done** (the last quest done, or the mission left after quest 4:
quest 5 may be put off; `mission_done` in `.orkcraft/mission.json`) is the campaign's first chapter
(`growth.chapters`), which INV's paths read: the deed *Mission 1*, the portrait's stage 2, and the item `first-cart`
(`realm/items.py`, `.orkcraft/items.json`). Screenshots: [img/m1/](img/m1/).

## 10. Mission 1b: Proof before the gate (design, 2026-10-14, night; not built)

The campaign's next mission (§8, §9.4). **One idea: a check inside the loop.** The ork runs the project's tests on
its own work and reworks until they pass, so what reaches the person at the Review gate has already been checked,
and the waybill shows each round. It is built on Mission 1's town: the Task board, the Agent pool, the Review gate.

### 10.1 Where the check lives, and how it looks

- **The check belongs to the Agent pool, not a new building.** The pool already runs a test command on an ork's
  branch after the ork (`test_cmd`, core/workers/barracks_review.py) and sends a failed run back to the same ork
  (`REWORK`, at most `max_reworks`, then 🔥 for the person). Mission 1b turns that on and shows it. The Test bench
  stays frozen: a mission never unfreezes a building (§8 rule 3).
- **In Camp: the proving siding.** It is a short siding beside the Agent pool, drawn the way the Task board's siding
  is (layout.js `SIDING`): two straights, a buffer stop, and a semaphore arm at its mouth. A cart leaving the pool
  rolls onto the siding first. The arm says the verdict by its position, never by colour (yellow and red stay the
  person's signals, design-system-v3.md §5):
  - **tests pass:** the arm goes up, the cart backs out and rolls on along the line to the Review gate;
  - **tests fail:** the arm stays down and the cart rolls back into the pool's door. Its chip reads `round 2 · tests
    failed`, and the ork at the pool takes it again. **This is the cart going round again**, seen from across the
    camp without opening anything;
  - **out of rounds** (`max_reworks` spent): the cart stands on the siding with 🔥, and the person's console opens on
    the ork's last run, as any stuck cart does today.
- **In Office:** the pool's row shows `round 2 of 3 · tests failed`, then `tests ✓ · 2 rounds`. Same words, no siding.
- **The waybill** (cart-waybill.md, `Hop.round`) gets one row per round at the pool: the round, what the ork changed
  (its commit count), the verdict (`tests ✓` / `tests ✗` with the last lines of the failure, folded), and that round's
  tokens and time. Its foot adds them up: `2 rounds · 1 failed check · 🪵 41k`. The cost of a rework is never hidden:
  it is the price of proof, and the score counts it (the-score.md).

### 10.2 The quests

The quest log and its rules are Mission 1's: one objective at a time, one press, the price said before it, skippable
at every step. The ork that works is called by its orkish name, a Grunt; the buildings by what they do.

| quest | the Workchief | what happens | time · cost |
|---|---|---|---|
| **1** | "Boss, the Grunts hand you work they never tried." | **Set the check.** The Workchief finds the project's test command (`pytest`, `npm test`, `go test ./...`, `cargo test`, `make test`, read from the project's files, no model) and the person confirms it or types their own: one press. It is run once on the main branch. A red main stops the quest and says so plainly ("the tests fail before any ork touched them: fix them first, or pick a narrower command"). The proving siding is laid beside the pool | ≤ 2 min · free, no model |
| **2** | "Watch one fail, then pass." | **A drill.** Called a drill on its card and in the Workchief's words (§2 rule 5). A scripted Grunt's first round fails the check and its second passes. The check's verdicts are scripted too: no model, the project untouched. The person watches the cart go round again, then opens its waybill: two rounds | ≤ 2 min · free, no model |
| **3** | "Now for real." | **One real card**, chosen by the person from the board (Mission 1's quest 4 left some there), run on a branch with the check on. Its price is said first: one run on the main tool, a budget of $1.00 on the pool for the quest (taken off when it ends, as quest 5's is). It reaches the Review gate already checked. The person reads its waybill and lifts the barrier, or sends it back with a reason: then the round count goes on | ≤ 10 min · price said first |

Quest 3 needs the Security reviewer on, as Mission 1's quest 5 does. It works on a branch and nothing is merged
without the person.

### 10.3 What offers it

**The trigger:** a result passed at the gate that later fails its tests. Any one of these counts:

1. the pull request of a pool task passed at the Review gate shows a failed check (`gh pr view --json
   statusCheckRollup`, read when the pool settles its pull requests: `settle_prs`);
2. a pool branch that was passed and merged is reverted within 14 days (the git log, read the same way);
3. the person sends a result back at the gate, or rates it 👎, with a note that says it broke (the reason chip
   "did the wrong thing" with a note matching test, build, fails, broken).

Mission 1b is offered **once**, in the Workchief's line after the next morning brief, while the pool has no
`test_cmd` set. It is a new chapter, not an improvement, so it never goes in the 💡 list. The line names what
happened: "Boss, *Fix the login form* passed your gate on Tuesday and broke its tests on GitHub. Want the Grunts to
prove their work before you see it?" A "Not now" is remembered for 14 days. **The fallback** (§8): offered anyway
three days after Mission 1 is done, if none of the triggers fired.

### 10.4 The finale and the rewards

- **The finale:** the checked cart passes the gate and rolls on as in Mission 1's finale (`Finale`), its chip showing
  what it really cost and how it was proved: `tests ✓ · 2 rounds · 🪵 41k` (and `$` on an API key). It is green when
  below the town's average per result, as any launched cart is. This cart is real work: it goes down its real roads
  (a pull request, the Publisher if there is one), and nothing is merged without the person.
- **A deed per quest** (`quest1b.check`, `quest1b.drill`, `quest1b.real`, in `growth.MISSION_DEEDS`, listed once
  earned) and **"Proof before the gate"** for the mission.
- **The item:** *the proving stone*, a whetstone on a plinth, earned once. It is a file like every item:
  `design-system/items/proving-stone.json`, `by: "mission"`. Its sprite is a stand-in until GEN draws it. It lands in
  the inventory quietly (v3-prompts §14 rule 4).
- **No stage of its own.** 1b is not one of the campaign's chapters. The portrait's paths stay as INV built them:
  stage 2 by Mission 1, stage 3 by Mission 2 (the second chapter), a lean week or a building at II. Mission 1b helps
  toward stage 3 only the honest way: proved work gets fewer 👎 and reworks, so the quality guard holds and lean
  weeks count. Nothing a person can do is locked behind it: the pool's `test_cmd` is in its settings for anyone,
  mission or not.

### 10.5 What it reuses, what is new, and a rough size

**Reused from Mission 1 and main:** the mission engine (quests, one press, `tick`, skip, the event log's
`quest_started` / `quest_done` / `quest_skipped`), the drill's script (`drill.json`), the pool's `test_cmd` and its
rework loop, `Hop.round`, the waybill, the Review gate's barrier and *Lift the barrier*, Mission 1's `Finale`, the
quest's budget on the pool (quest 5's), and the deeds, items and stage paths (realm/growth.py, realm/items.py).

**New code:**

| piece | where | size |
|---|---|---|
| missions as data files (§8 rule 2): Mission 1's quests moved out of `realm/mission.py` into `missions/1.json`, 1b in `missions/1b.json`, checked by a test; `mission.json` keyed by mission (Mission 1's file read as before) | realm/mission.py, core/mission.py | 1 day |
| the test command found and run once on main | realm/mission_work.py | ½ day |
| the drill's scripted check (`"check": [false, true]` in `drill.json`) | core/workers/barracks_review.py | ¼ day |
| a check's round on the bus (`pool.checked`: round, verdict, the failure's tail), so carts and the waybill see it | core/workers/barracks_review.py, gui/state.py | ½ day |
| the proving siding and its arm, a cart backing into the pool | js/camp/layout.js, js/camp/carts.js | 1 day |
| the waybill's rows per round and its foot | js/camp/waybill.js, gui/views/loot.py | ¼ day |
| the trigger: a passed result's failed checks or revert, the 👎 note, the one-time offer | core/workers/barracks_review.py, realm/gitinfo.py, core/mission.py | 1 day |
| deeds, the item's file and stand-in sprite, tests (unit, a browser test for the siding and the rounds) | realm/growth.py, design-system/items/, tests/ | ½ day |

**About 5 days**, in that order. Moving the quests to data files comes first: it is the price of a second mission
and is owed by §8 anyway.

### 10.6 Open

1. **A project with no tests.** Quest 1 could offer a linter or a type check in the tests' place (`ruff`, `tsc
   --noEmit`), or stop and say so. My proposal is to offer the linter, said plainly: "no tests found; the check will
   be the linter".
2. **A slow test suite** (over two minutes) makes every round slow. Quest 1 could time the run on main and propose a
   narrower command (the changed package's tests) when it is slow.
3. **A failed check on GitHub that is not the ork's** (a flaky test, a red main) must not count as the trigger.
   Count it only when main was green at the same time.

## 11. From the drills to the person's own camp: the charter (the owner's question, 15 October; design, not built)

The question: Mission 1 teaches with drills; how does the person move from the tutorial to a camp built for **their
own goal**? Answer: **one moment, the charter, between the drills and the first real work** — the camp is given its
purpose, in the story's words, and everything after is real work towards it.

**When:** at the start of quest 4, the first real work (§3), right after the drills of quests 1–3 and the look switch
of 3½. Never before Mission 1 (the onboarding asks as little as possible at the start, B6).

**The Workchief:** "Boss, the drills are done and the Grunts are restless. What are we building here?" Three
answers, one screen, the class's chips already known:

| answer | what follows |
|---|---|
| **"My project"** (the default for a developer: the project folder or repository the town already has) | one line of the goal in the person's words ("a co-op roguelike, a playable demo by December"); optional: a deadline. The Workchief reads the repository (its README, open issues, TODOs) and proposes **the first three to five cards** towards the goal, each with its price said; the person keeps, edits or drops each, and they land on the Task board as real cards. Quest 4 then takes its first real work from them (the listeners' issues stay as the source when there is no goal line) |
| **"A routine to automate"** (no project yet, or a manager's class) | four ready routines to pick one from: the inbox sorted by rules, a weekly report, meeting briefs, a research digest; the picked one becomes the camp's goal, and Mission 2 (a process that comes back, §7) is offered at once instead of later |
| **"Just looking"** | the camp stays a sandbox with the demo's drills; the charter can be given any time from the Town Hall |

**In the camp:** the charter is a **banner on the wall band** (§20 of the decisions), the goal's line written on it,
by the lookout; a click opens it (edit the line, the deadline, the cards it spawned). It is the camp's purpose seen
every day, not a score: **milestones, not points** (§8's rule that nothing a person can do is locked behind play). A
card towards the goal wears the banner's small mark on its waybill, so the person sees which work serves it.

**After the charter, the campaign serves the goal:** each later mission is offered when the real work shows its
moment (§8: failed checks → 1b, the same files read again → the Wiki's mission, …), on the person's own cards. The
plots of the person's quarter (decisions §20) appear after Mission 1 and are chosen by the goal as well (a game's
goal → the UX bench and assets; a library → the Test bench and Branches & PRs).

**The story:** the person's class hired the camp (v3-prompts §13: a Jira Lich, an Indie Knight…); the charter is the
contract. The Workchief's lines may joke; the goal line and the cards' prices are said plainly (CLAUDE.md, the voice).

**Size:** the charter screen and the banner, about 1 day; the first cards from the repository and the goal, one
model call with its price said, about 1 day; the routine path reuses Mission 2's design. **Priority:** P0 for
activation, built after the owner has played Mission 1 (§9) and with 1b's order decided then. Not started.
