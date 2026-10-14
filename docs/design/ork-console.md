# Design — every ork in reach: one status, one console

Status: proposal 2026-10-12, nothing built. Talked through by the owner as product and UX ("think it through before
any code"). Builds on [select-a-building.md](select-a-building.md) §2 (the Warchief's line is the selected building's
command card), [warchief-line-and-cards.md](warchief-line-and-cards.md) §0 (buildings with and without a view),
[yards.md](yards.md) (an ork lives only where a model thinks), [roads-and-orcs.md](roads-and-orcs.md) and
[steward-at-work.md](steward-at-work.md) (stewards and their tier), [calm-town.md](calm-town.md) (the HUD: Stop all,
Answers, Agents). The Town Hall's roles are in [town-hall-roles.md](town-hall-roles.md).

**Priorities** (the owner asked for hard ones, 2026-10-12), used in §11 and on every later section:

- **P0** — before the first outside testers, and only for the buildings in the demo GIF and the testers' first
  fifteen minutes. The launch plan waits on these.
- **P1** — after the testers, decided again by what they showed.
- **Later** — worth doing, not this quarter.
- **No** — not needed; said so, with the reason.

## 1. Why

The town shows the buildings well: what they are, which roads join them, where a cart goes, even which building a
failure came back from. It shows the **orks** badly. Talking to an ork is a toast in one place, a dialog in another,
a part of a building's Work window in a third. Its session runs in a terminal nobody sees.

The owner's daily use says what that costs: a question that reaches a burning hut is the exception. Not because the
orks are sure, but because a session run out of sight has **no way to ask**. So it guesses, and its guesses go into
the result unseen. The person sees a finished cart and cannot tell which parts of it were assumed.

Not steering every ork was part of the idea from the start, and it stays the default. But a person who runs agents
for real, and above all now, while the buildings' orkestration still often goes wrong, has to be able to **look in
and step in when needed**: locally, where the ork works, at a low cost in attention, never as a chat list to watch.

The goal of this design:

> **Make an ork's uncertainty visible and cheap to deal with, without turning it into a stream of interruptions.**

Calm by default, full control on demand: every ork's state in one look, every ork's session one click away.

### 1a. Check it first (no code)

Before building, check the guess on the owner's own sessions. Open the logs of 10–15 recent ork sessions, from
several buildings, good runs and bad ones, and write down every place where an ork assumed something ("I'll
assume…", a choice made without a reason, an error worked around instead of reported). Per assumption: right,
wrong or unimportant, and would the owner have wanted to be asked?

| session | building · ork | assumptions | wrong | would have asked |
|---|---|---|---|---|
| | | | | |

- One or two assumptions that matter per session, some of them wrong: the ask channel (§4) comes first, and part
  of today's "the orkestration works badly" is unseen guessing.
- Few, and almost always right: the problem is mostly seeing state (§5, §6); the ask channel can wait.

## 2. The words: ork, session, building

| | what it is | what it holds | a 👎 on it says |
|---|---|---|---|
| **Ork** | a role | its prompt (the role), its tier, its tools (by default its building's), its **Autonomy** | the role is badly put |
| **Session** | one run of an ork | its AI tool (the harness), its spend and tokens, its history, its result and the assumptions marked on it | this answer was bad |
| **Building** | a way of working with information | its view (or none, [warchief-line-and-cards.md](warchief-line-and-cards.md) §0), its quick actions, its flow (in turn, in parallel, a debate, a router first, a check last), its code part (chains, scripts) | its flow or its view is bad |

A building's goal shapes how its orks are started and how its work is shown, never the orks' roles or models.
Some buildings have a steward that routes, checks or sorts what comes in; part of their work is still code, and
some (the yards) are code only.

Decisions this takes:

1. **The tier belongs to the ork.** Today a steward runs on its building's model
   ([steward-at-work.md](steward-at-work.md) §2, [warchief-line-and-cards.md](warchief-line-and-cards.md) §7). This
   changes that on purpose: a role has the tier that suits it; the AI tool and the spend are the session's.
2. **Autonomy belongs to the ork; gates belong to the building.** Autonomy says what an ork may do without asking
   (§4). A gate in a flow (the Review gate's rules) says where a cart waits for a person. Two words for two things,
   or a person will not see why an ork with full Autonomy still waits.
3. **Tools: the building gives the default set, an ork may narrow it, never widen it.** Widening goes through the
   building, where the Warder and the person see it.
4. **Three 👎, three meanings:** on a session (this answer), on an ork (this role), on a building (this flow or view).
5. **An ork is a role; runs side by side are sessions** (decided 2026-10-12). Three Grunts on tests at once are
   one ork, the Grunt for tests, with three sessions. Its history and its 👎 gather on the role, so a worse persona
   shows. An ork slot (🥩) is taken by a session, not by a role.
6. **A role is an expertise wherever it works.** The Test bench is the Mechanic's place of work, not its owner; the
   same role may work in several buildings and flows, each run a session there
   ([town-hall-roles.md](town-hall-roles.md)).

## 3. What stays as built

- The Warchief's line is the selected building's command card: its steward's face, its three quick actions (Q, W,
  E), its field asks its steward ([select-a-building.md](select-a-building.md) §2).
- Nothing selected, the line is the Warchief's: Build and Improve (the Town Hall's actions, the hall itself unseen).
- A building's setup is done in the line ([select-a-building.md](select-a-building.md) §7): the Town Hall's command
  card, changed.
- Orks drawn only where a model works; a yard calls one when it needs it ([yards.md](yards.md)).

This design adds the second half of the line, the ork's console (§7), one status for every ork (§5), and the ork
slots list in the HUD (§8). It takes away the ways of talking to an ork that it replaces (§10).

## 4. Uncertainty: ask, assume and mark, or decide

An ork that is unsure does one of three things. Its **Autonomy** says which, so Autonomy is a behaviour the person
sees, not a checkbox:

| | when | what the person sees |
|---|---|---|
| **Ask and wait** | a costly or irreversible choice, or low Autonomy | ❓ on the ork (§5); 🔥 on its building if the flow cannot go on without the answer |
| **Assume and mark** | a choice that can be undone but is not obvious | a mark on the **result**: "2 assumptions". Read when the person wants; correct one and run again |
| **Decide quietly** | routine | nothing; it is in the session's history |

Assumptions never raise ❓. A ❓ that is up nearly all the time stops being seen; ❓ stays for "I cannot go on
without you".

For any of this an ork needs a **way to ask and a way to mark**, in every AI tool, also when its session runs out of
sight. How (a tool Orkline gives every ork, the harness's own question form, a block at the end of the run) is an
open question for engineering (§12).

## 5. One status, everywhere

The same states, the same marks, wherever an ork or a building is drawn: on the town, in the ork slots list, in the
console, in a session's history. Never colour alone: a shape and a short word too, so the Office look and a person
who does not tell colours apart read the same.

**An ork:**

| state | Camp | Office | asks for attention |
|---|---|---|---|
| resting | Zz | Resting | no |
| thinking | a thought bubble, and a short "on what" | Thinking: <what> | no |
| using a tool | the tool's sign and name | Running <tool> | no |
| result ready | a scroll; "+ N assumptions" when it has some | Done · N assumptions | softly |
| **asks** | **❓** | **Asks** | **yes** |
| error | a red mark | Error | yes, through its building |
| stopped | a grey mark | Stopped by you | no |

**A building:**

| state | Camp | Office | means |
|---|---|---|---|
| working | the type's motion (the mill turns, the catapult throws) | Working | its flow runs |
| idle | still | Idle | nothing to do |
| **burning** | **🔥** | **Stopped: question / error** | its flow stands and will not move without you: an ork's question blocks it, or an error |
| **smouldering** | smoke, embers | Stopped by you | you stopped its work; it waits for Run again or Drop (§9) |

The two signals live on two levels, as the model does: **a question is the ork's, a stop is the building's.**

- One Grunt of five in the Agent pool asks; the others work on: ❓ on that Grunt, the building does not burn.
- A building's only ork asks and nothing goes on without the answer: ❓ on the ork **and** 🔥 on the building; the
  building's hint says why and the answer can be given from it.
- A building's script fails, no ork in it: 🔥 without ❓.
- The person stops the work: the building smoulders. No fire for what the person just did; a building left
  smouldering long (a day) is named in the morning brief.

**By zoom:**

| zoom | shows |
|---|---|
| map | only what needs the person: 🔥 on buildings, the number of ❓ beside a building |
| overview | the orks as small marks with their state, by their building |
| close | the orks in their building's yard with their bubbles; for the selected building only, the lines between its orks (who hands work to whom), as roads are drawn brighter for a selected building today |

## 6. Four depths

Each depth is reached only by the person's own move. The town lifts the person on its own only to depth 0, and only
for a question or an error. Everything else is pulled, not pushed.

| depth | reached by | shows | cost in attention |
|---|---|---|---|
| **0. A look** | nothing | 🔥 and ❓ counts; nothing else moves | none |
| **1. A peek** | the mouse over an ork or a building | one line: its state and on what ("planning the task", "running pytest", "2 assumptions") | least |
| **2. Selected** | a click | the console, folded (§7) | low |
| **3. In** | unfold the console | the whole session (§7) | full |

The promise to say in the onboarding and the README: **any ork's session can be opened, as a tmux session is
attached: seen, answered, stopped.** A person who never does it still knows there is no black box.

## 7. The line in two parts

The line at the town's foot, today the Warchief's or the selected building's command card, gets a second part:

```
┌─ building part (built) ──────────────────────────┬─ ork part (new) ─────────────────────────────────┐
│ [steward's face] Agent pool                       │ [Grunt ❓]  "Merge into main or into dev?"         │
│ Q Add a task · W Run · E Review · ⋯              │ [main] [dev] [Reply…]   ⏸ Stop   $0.31 · claude │
│ portraits: [Grunt ❓] [Grunt ⚙] [Grunt 💭] …      │ ▸ unfold: whole session, history                  │
└───────────────────────────────────────────────────┴───────────────────────────────────────────────────┘
```

**What is in it:**

| selected | building part | ork part |
|---|---|---|
| nothing | the Warchief: Build ▾, Improve | the Warchief's own session (today's line) |
| a building | its command card (built) and a row of **its orks' portraits** with their state (§5) | the ork waiting on the person, if one is; else the building's steward; else empty |
| an ork (on the town or a portrait) | its building's command card | **that ork's console** |

**Built (A5, 2026-10-14):** folded and unfolded, for an Agent pool's ork in full and for any other ork its row
(js/slots.js, js/orkconsole.js; the data from core/slots.py `console`). The live terminal is the ork's own session,
opened on Take over or Resume; pinned is not built (the console stays until closed anyway). Gists come from a
`GIST:` line in the ork's `asks` block (§20).

**The console has three sizes:**

- **folded** (depth 2): its state, its last question or output, Reply, Stop, the session's spend and AI tool;
- **unfolded** (depth 3): the live terminal of the session (xterm, `gui/static/vendor`), text can be copied, the
  person can type into it; above it the ork's sessions, each with its spend, tokens, AI tool, 👍 / 👎 and its
  assumptions; a link to the ork's prompt and tier in its settings;
- **pinned**: stays open while the person moves around the town.

**The terminal is the truth; forms are on top.** The live terminal shows what the AI tool really does. Where an AI
tool hands its question over in a structured way (Claude Code's question form, its hooks), the console shows it as
buttons; where not, the question is the terminal's text and Reply types into it. Never a different behaviour per AI
tool that the person has to learn: the buttons are a shortcut, the terminal always works.

Work windows give up the orks' chatter: a building's Work is about its data. What its orks say and ask goes to the
console.

## 8. The HUD: ork slots and what waits

Today's 🥩 (ork slots: running agents against their limit) becomes the town's one list of working orks. The town is
the local way to an ork, this list the global one; both lead to the same console.

```
🥩 3/8          🔥 1 · ❓ 2          [Stop all]
working         waits for you
```

A click on either opens the same list, sorted by work or by attention. One row per ork:

```
❓ Grunt · Agent pool          asks: "merge into main or dev?"      4m   $0.31   ⏹
✓ Mechanic · Test bench        done · 2 assumptions                 1m   $0.08
⚙ Grunt · Agent pool          running pytest                       7m   $0.54   ⏹
💭 Alchemist · UX bench        thinking: the card's layout          0m   $0.02   ⏹
💭 Lookout · External listeners sorting what came in               0m   $0.01   ⏹
```

- Waiting first, then the longest running: a long session that never asks is worth a look too.
- A click on a row moves the camera to the building, selects the ork and opens its console. The list does not repeat
  the console, it leads to it.
- ⏹ stops one ork softly (§9) without leaving the place.
- The marks are the town's (§5): the list is the test that the status is one.

**Answers** (today's button for the orks' questions) folds into ❓ N: the same list, sorted by attention.

**Stop all stays**, one button, always seen, beside 🥩 as one block "what runs". The list is for finding out; Stop all
is for not finding out: something is wrong, stop everything now. It also stops scripts and browsers, which 🥩 does not
count, and "Stop all halts everything" is a promise the README makes to a person letting agents into their project
for the first time. The list repeats it as its first row for whoever already opened it.

## 9. Stopping and slots

- **⏹ on one ork is soft:** the tool call in flight ends, the session is kept so it can go on later. **Stop all is
  hard:** every process is ended at once.
- **Stopped work is interrupted, and so is its building's flow:** the cart is marked "stopped by you", the building
  smoulders (§5), the console offers **Run again** (the session goes on) and **Drop** (the cart is closed as dropped).
- **A waiting ork takes no slot.** It spends nothing while it waits. Its building stands, which the building's 🔥 says.
- **An answered ork goes on at once, over the limit if need be.** The limit holds new work back, never an answer the
  person just gave: answering and seeing nothing happen is the worst outcome for the move this design wants cheap.
  Over the limit is shown as it is (`🥩 10/8`); new work waits until the count is under the limit again.

## 10. What goes away

Every toast, dialog and Work-window part this replaces goes in the same change, or the town gets a fourth way to talk
to an ork instead of one. To fill in from the code before stage 1:

| today | where | replaced by |
|---|---|---|
| Answers (HUD button) | `calm-town.md` | ❓ N and the ork slots list (§8) |
| the Agent pool's ork tabs: terminal, Take over, Hand back, recent work | its Work (`js/buildings/barracks.js`) | the console unfolded (§7, `js/orkconsole.js`), A5 |
| the Agent pool's question strip and answer dialog | its Work | the console's pinned questions (§20) and the task on its large card |

## 11. Stages and priorities

| | what | § | priority |
|---|---|---|---|
| 0 | the log check | §1a | **P0**, no code; decides how big the ask channel is |
| 1 | a way to ask and to mark assumptions, Claude Code first; its questions pinned on top of the answer | §4, §20 | **P0** |
| 2 | one status on the town: ❓ on orks, 🔥 / smouldering on buildings; every wait says why and until when, and a task where it goes next; an ork's status names the cart it works on | §5, §19, [cart-waybill.md](cart-waybill.md) §4 | **P0** |
| 3 | the ork slots list, 🔥 · ❓ counts, Stop all beside it | §8 | **P0** |
| 4 | the console, folded and unfolded, for the selected ork | §7 | **P0** |
| 5 | the removals the console replaces | §10 | **P0**, in the same change as 4 |
| 5b | a local full-detail event log; the events the P0 checks need; every wait logged with its reason and length | [dogfood-logs.md](dogfood-logs.md) §3 | **P0**: without it the checks of §13 cannot be measured |
| 5c | the night's work off by default in a new town; External listeners offer GitHub, a schedule, a webhook and a file only | [cut-list.md](cut-list.md) | **P0** |
| 5d | the first session as Mission 1: a drill cart, real work on the person's repository, two orks at once; the onboarding form cut to the AI tools found | [first-mission.md](first-mission.md) | **P0** |
| 5e | a colour pass by tokens: ground off the buildings' hue, idle dimming softened, warm colours for signals only, roads seen, one display face | [color-pass.md](color-pass.md) | **P0**: the demo GIF is judged on it |
| 6 | the Agent pool's lanes as roles with session chips | §14 | **P0**, the lanes only (they exist); the data model behind them is P1 |
| 7 | Work keeps data and flow; Info split into the building's and the ork's | §15 | **P1** |
| 8 | the Town Hall's roles folded, 11 names to 8 | [town-hall-roles.md](town-hall-roles.md) | **P1**, before the ork's Info ships (or it ships 11 role cards) |
| 9 | a yard's failure: the Warchief sorts it, the Mason repairs | §16 | **P1** |
| 10 | tier and Autonomy on the ork in settings; a session's 👎 apart from its ork's | §2 | **P1** |
| 11 | quick actions for every building | §7 | **P1** |
| 12 | the yard with lines between its orks; forms over every AI tool's questions | §5, §7 | **Later** |
| 12b | the game's score (wood and limit per accepted result, guarded by quality) and one 💡 list of improvements in the HUD | [the-score.md](the-score.md) | **P1** |
| 13 | a cart's waybill in the Inspector, opened from anywhere (takes in a cart's price and load) | [cart-waybill.md](cart-waybill.md), §17 | **P1**, after a cart's id across stops |
| 14 | the phone: the same ork slots list, console and waits, built once for both ([cut-list.md](cut-list.md) §3a) | §7, §8, §19 | **P1**, right after the console |
| 15 | a hidden Town Hall feature for reviewing the person's own project | §18 | **No** |

P0 is for the buildings in the demo GIF and the testers' first fifteen minutes only, not every type.

## 12. Open questions for engineering

1. How does an ork's session run today: one headless call, or a live terminal (PTY)? A headless call cannot be
   answered or asked more; this may be the root of §1.
2. What does "open the session" mean for each AI tool (`claude`, `codex`, `agy`): attach to a live terminal, or resume
   a kept session with the person's message?
3. How does an ork ask and mark an assumption the same way in every AI tool, also out of sight: a tool Orkline
   gives every ork (an MCP server, as all three take MCP), the AI tool's own form, or a block the ork writes at the
   end of its run? Which of them works with each tool run without a terminal is to be checked, not assumed.
4. Spend per call in the history: can each AI tool's run be priced on its own, as today's 🪙 does per building?

## 13. How we know it works

- In the testers' fifteen minutes (the launch plan): "one of the orks has asked something; find it and answer it."
  **4 of 5 do it in 30 seconds or less, without a hint.** If not, the status (§5) is the problem, not the console.
- The owner, after two weeks: the log check (§1a) again, on sessions run with the ask channel. Fewer unseen
  assumptions, and the ones left are marked.
- No outside tester calls the orks "a black box" when asked how the town works.

## 14. An ork's runs side by side on its building's card (P0: the lanes)

An ork is a role, its runs are sessions (§2, decision 5). On a card a role is shown once, its sessions as chips in
the one status, as an RTS shows a squad: one portrait, a number, each unit's state small.

The Agent pool's medium card, a lane a role (today a lane an ork, [warchief-line-and-cards.md](warchief-line-and-cards.md) §4):

```
Grunt · tests       ⚙ ⚙ ❓      3 at work · 4 waiting
Grunt · frontend    💭           1 at work · 0 waiting
Grunt · any work    Zz           —
```

- A role whose session asks shows ❓ on its chip and on its head.
- A chip opens the console on that session; the role opens the console on the role: a row of chips over it
  (`#1 ⚙ · #2 ⚙ · #3 ❓`), the asking one first, else the longest running; below, the role's history.
- By zoom: the map, the building's count and ❓; overview, one head with `×3`; close, three orks under one hat in the
  yard, a bubble each.

## 15. Work keeps data and flow; two Infos (P1)

**Later the same day (2026-10-12): Work goes altogether** ([lighter-buildings.md](lighter-buildings.md) §2). What this
section says Work keeps moves to the building's card (its large size in place); the rest of the section, the test
and the two Infos, stands.

**The test for any element:** take every ork out of the building. Does the element still make sense? Yes: it is the
building's (Work or the building's Info). No: it is the ork's (the console or the ork's Info).

**Work keeps:**

1. **The flow strip**, one line on top, the same on every building: in → at work → waiting at a gate → done, with
   counts; stopped and failed on it too. Where it stands, without reading a log.
2. **The building's data**, its own per type: tasks, files, events, mail, diffs. What the window is opened for.
3. **Results**, each with its state, its "N assumptions" and its 👍 / 👎; a click on one opens the session that made
   it in the console. This is the one link from Work to the orks.
4. **Actions on a row of data** (take a task, open a file, pass the gate). The building's own actions (Run, Check
   now) are its command card's Q, W, E, never repeated as buttons in Work.
5. **An empty state:** one sentence on what the building does, one action.

**Work gives up:** the orks' logs and thinking (to the console), their questions (❓, the console), the AI tool and
tier pickers (the ork's Info), a session's spend (the console; the building's total stays in its Info), settings and
rules (the building's Info).

**The exception is the Agent pool**, whose data are partly its orks. Its lanes stay in Work as data about the tasks
(topic, queue, what is at work); the head in a lane is the one status and opens the console; no ork's log in a lane.

**The building's Info** — what it is and how it works: name, type, goal, card size; the flow's shape (in turn, side
by side, a debate, a router first, a check last) and its gates; roads in and out and their road rules (a road rule
is the flow, even when its steward carries it out); its code part (chains, scripts); its record (runs, done,
failed, a week's spend, 👍 / 👎 with notes); Watch, Report, Redesign (the upkeep of its view and flow); **its orks**,
each a link.

**The ork's Info** — who it is and how it thinks: its role (prompt, editable; topic or persona); its tier; its tools
(the building's set, what is narrowed marked); its **Autonomy** (ask, assume and mark, decide; it moves here from the
building's Freedom); its default AI tool (by tier, or a preferred one; the real one is the session's); its sessions
(date, length, spend, AI tool, assumptions, 👍 / 👎); a 👎 on the role with a note; the buildings it works in.

Two windows, linked both ways, never two tabs of one: tabs would glue back together what §2 takes apart. The
building's Info from ⚙ on its card or ⋯ in its command card; the ork's from its name in the console, a right click
on its portrait, or its row in the ork slots list.

**Spend has one source, the sessions**, and is only summed elsewhere: a session (the console), an ork (its Info), a
building (its Info), a cart's way (§17), the town (the HUD's 🪙). Never counted twice two ways.

## 16. A yard's failure has an owner (P1)

A yard has no ork of its own (yards.md). When it fails:

1. its flow stands: the building burns (§5);
2. **the Warchief** sorts it out: a cheap session that reads the error and decides who takes it;
3. a broken script or chain goes to **the Mason**, who built it: a fix proposed, the person applies it as a builder's
   change is applied today;
4. a cause outside the code (mail access ran out, `gh` missing) is not repaired: the Warchief says plainly what is
   needed from the person.

No new ork. The Mason builds, the Mason repairs.

## 17. A cart's price and load (Later)

**2026-10-13: taken into the cart's waybill** ([cart-waybill.md](cart-waybill.md) §2), P1. The hints and the outliers
below stay as written.

A cart gathers spend on its way: one mail from Mail to a sent reply, one task from the board to a pull request. Two
amounts, shown apart:

- **🪙 the way's price:** what every session on its way has spent on it so far. The past.
- **🪵 the load:** the tokens it carries on (text, context, attachments). The future: every next building reads it,
  so a growing load is why spend compounds.

Calm by default: the cart's heap grows with its load (no number); its price tag on the mouse ("$0.07 · 12k tokens ·
3 stops"); a road's mean price per cart on the selected building's roads (`≈$0.04 / cart`); a soft mark only on an
outlier (over three times its road's median, or a load more than doubled at one stop). A click on a cart opens its
**waybill**: each stop, its building, its session (a link to the console), its price, its load before and after.

Hard parts: a session that handled ten carts at once (split evenly, and the waybill says "a share of a batch of
10"); spend with no cart (Watch, the night's council, the audit) is the building's and the town's overhead, never a
cart's; whether a cart knows today which sessions it went through is a question for engineering.

**Why Later:** it answers a question no other tool in this class asks (what does one unit of work cost from intake to
result), and it is the Treasurer's best data. But no first user needs it to see who works and who waits.

## 18. Not a Town Hall feature: reviewing the person's own project (No)

Asked 2026-10-12: a night's look at the person's own project and its quarter's goals, with a product manager, a
product designer and an AI architect. **It is a building's work, a Review board's, not a hidden Town Hall flow.** The
Town Hall and its flows (the Elders, the audit, the builder) look after the town itself; the person's work is done by
buildings, so its flow shows on the map with its spend, its exits and its 👎. The Town Hall's roles are written for
Orkline and would give the wrong advice on another project.

How it is set up today, by hand: the goals in a file of the project (`docs/goals-q4.md`); a schedule in External
listeners, **weekly**, plus a run when that file changes (a quarter's goals do not change overnight; three opinions a
night are paid for the same answers), or the Calendar when it is for a meeting; a Review board whose purpose says
what to judge, its clan proposed by its steward and cut to the three roles; one exit "To me" (the morning brief), and
"To the Task board" for actions if wanted; no veto (opinions, not a gate).

To check on the first run: does a clan member read the project's code, or only the document it is given? An AI
architect needs the code's context.

**Later, not a hidden feature: a recipe.** The person tells the Warchief what they want and it lays the whole set
(schedule → Review board with its clan → the brief), all on the map and all editable. A good thing for buildings
from the community. And later still a role may be an expertise whose context the building gives, so the Farseer
could sit on the person's own clan.

## 19. Every wait says why, until when, and how to skip it (P0)

Asked 2026-10-12. The owner opens the Task board's and the Agent pool's Work panels every day, not for their data but
to find out **why something is not moving**: when a task will be made or started (there is a delay), how to hand a
task on, why an ork does not start or what it is doing. The cure is the status, not a bigger window: the same
unseen state as §1, on tasks and carts as well as orks.

> **Whatever waits says why, until when, and offers the way to skip the wait**, on its card and in its row of the
> ork slots list, in the one status of §5.

**The waits that exist today** ([barracks-planning.md](barracks-planning.md), [town-time.md](town-time.md)), each with
its plain line:

| why it waits | the line | the way past it |
|---|---|---|
| its plan waits for the person (Autonomy: propose only) | "waits for your yes to its plan" | **Approve** (the console opens on the plan) |
| its plan waits its timer (Autonomy: apply if unanswered) | "starts on its own in 4 min" | **Start now** |
| another task first (`after`) | "after «Fix the login»" | a link to that task |
| no ork for its topic yet | "hiring a Grunt for design" | — |
| no free ork slot | "no free slot (8/8)" | **Run anyway** (over the limit, said so) |
| held for a limit's reset | "held by the Treasurer until 14:00" | **Run anyway** |
| the steward is sorting or planning it | "the steward is planning it" | the steward's session in the console |
| quiet hours | "starts at 08:00, after quiet hours" | **Start now** |

A wait with no line in this table is a bug: either it gets its line, or it should not wait.

**Handing a task on.** A task's card says where it goes next: "goes to the Agent pool when ready (by its road)". With
no road out it says so: "no road out", and offers **Lay a road to…** the buildings that would take it. Handing on by
hand is the command card's: **Send to ▸** with the buildings on its roads.

**What it takes from the panel:** the Task board's and the Agent pool's daily opens
([lighter-buildings.md](lighter-buildings.md) §6) were all to answer "why is it waiting"; with this and §5 they are
answered on the cards. If the testers still open the panels for it, a line is missing.

In §11 this is part of stage 2 (one status), P0.

## 20. Long answers, lost questions: what is read first (questions P0, the rest P1)

Asked 2026-10-12: in Claude Code's phone app long answers are hard to read and a question is lost in them on a small
screen. The same holds on the desktop, only less.

**An ork's answer is shown in this order, on every screen:**

1. **Its questions, pinned on top**, each a card with its answers as buttons (or a field), until answered. Never only
   inside the text.
2. **The gist**, three lines at most: what was done or found.
3. **Its assumptions** (§4), each a line.
4. **The whole text, folded.** One press opens it; on the phone it opens as its own page.

**Where the gist and the questions come from:** the ork gives them as a short structured block at the end of its run,
through the same way to ask and to mark of §4. No second model call to summarise. An ork whose AI tool gives no such
block shows its last paragraph as the gist and its text as it is, and the console says so.

**Priority:** the pinned questions are **P0**, part of the way to ask (§4, §11 stage 1). The gist and the folded text
are **P1**, with the phone ([cut-list.md](cut-list.md) §3a).

## 21. A talk belongs to what it is about, never to a tab (P1)

Asked 2026-10-12: with today's tools the owner forgets in which tab or session something was talked through.

> **A talk lives on the thing it is about: an idea's card, a task, a building. There are no tabs of talks.**

- **On the card:** an idea's or a task's card holds its talks, each a session (§2) with its ork, its date and how it
  ended. Opening the card opens its talk; going on with it is going on with that session.
- **Recent talks**, one list in the console: the newest first, each with what it is about (a link to its card) and how
  it ended: **decided**, **waits for you** (❓, §5), or **left without a decision**.
- **A talk left without a decision** puts a soft mark on its card ("talked, not decided"), so it is not lost; the
  morning brief names those older than a day.
- **A talk started with no card** (from the Warchief's line) asks once, at its end, where it belongs: a new idea card,
  an existing card, or nowhere.
- **Search across all talks:** Later, once there are enough to need it.

With the phone's bar ([cut-list.md](cut-list.md) §3a: drop an idea, talk it through, send it to be built), **P1**.
