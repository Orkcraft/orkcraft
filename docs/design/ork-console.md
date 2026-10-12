# Design — every ork in reach: one status, one console

Status: proposal 2026-10-12, nothing built. Talked through by the owner as product and UX ("think it through before
any code"). Builds on [select-a-building.md](select-a-building.md) §2 (the Warchief's line is the selected building's
command card), [warchief-line-and-cards.md](warchief-line-and-cards.md) §0 (buildings with and without a view),
[yards.md](yards.md) (an ork lives only where a model thinks), [roads-and-orcs.md](roads-and-orcs.md) and
[steward-at-work.md](steward-at-work.md) (stewards and their tier), [calm-town.md](calm-town.md) (the HUD: Stop all,
Answers, Agents).

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
sight. How (a tool Orkcraft gives every ork, the harness's own question form, a block at the end of the run) is an
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
| | | |

## 11. Stages

0. **The log check** (§1a). No code. Decides how much of stage 1 the ask channel is.
1. **Before the first outside testers** (the main scenario: see who works and who waits, step in to one):
   1. the way to ask and to mark assumptions, for Claude Code first (§4);
   2. one status on the town (§5), 🔥 / smouldering on buildings, ❓ on orks;
   3. the ork slots list with 🔥 · ❓ counts and Stop all beside it (§8);
   4. the console, folded and unfolded (§7), for the selected ork;
   5. the removals of §10 that the console replaces.

   Only for the buildings in the demo GIF and the testers' first fifteen minutes.
2. **After the testers, by what they show:** quick actions for every building; tier and Autonomy moved onto the ork
   in settings; the yard with its lines between orks; forms over the questions of every AI tool; a 👎 on a session
   apart from one on its ork; the phone app (PWA) on the same status.

## 12. Open questions for engineering

1. How does an ork's session run today: one headless call, or a live terminal (PTY)? A headless call cannot be
   answered or asked more; this may be the root of §1.
2. What does "open the session" mean for each AI tool (`claude`, `codex`, `agy`): attach to a live terminal, or resume
   a kept session with the person's message?
3. How does an ork ask and mark an assumption the same way in every AI tool, also out of sight: a tool Orkcraft
   gives every ork (an MCP server, as all three take MCP), the AI tool's own form, or a block the ork writes at the
   end of its run? Which of them works with each tool run without a terminal is to be checked, not assumed.
4. Spend per call in the history: can each AI tool's run be priced on its own, as today's 🪙 does per building?

## 13. How we know it works

- In the testers' fifteen minutes (the launch plan): "one of the orks has asked something; find it and answer it."
  **4 of 5 do it in 30 seconds or less, without a hint.** If not, the status (§5) is the problem, not the console.
- The owner, after two weeks: the log check (§1a) again, on sessions run with the ask channel. Fewer unseen
  assumptions, and the ones left are marked.
- No outside tester calls the orks "a black box" when asked how the town works.
