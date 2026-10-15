# Design — who Orkline is for first

Status: decided with the owner 2026-10-13. Answers [open-questions.md](open-questions.md) Q1 and Q2. Everything a
new person sees (the demo GIF, Mission 1, the README, the posts) is made for this audience first. Builds on
[work-and-play.md](work-and-play.md), [first-mission.md](first-mission.md), [the-score.md](the-score.md),
[improve-buildings.md](improve-buildings.md) §12.4.

## 1. The three hypotheses the owner brought

| hypothesis | strong | weak |
|---|---|---|
| **People in IT**, overloaded, who after work look for flow (Stardew Valley; Factorio among engineers) | a real pain; Factorio is the exact image | "rest" and "improving work automation" sit badly together: for a burnt-out person an evening in a work tool is more work. What holds is not relief from stress but **optimising as play**. At work, many employers do not allow a personal tool running agents on their repositories |
| **Indie creators** building a factory for content (games, apps, a channel) | the clearest need for roads and automation; n8n frightens them | many are not developers, and Orkline needs Python, git and a CLI such as Claude Code: a wall before Mission 1. "A factory of AI content" risks a reputation for slop. The game look gives them least |
| **Game development**, the new wave | the look fits; assets; serious buildings | the old guard is hostile ([improve-buildings.md](improve-buildings.md) §12.4); the new wave is mostly the second hypothesis again |

## 2. The first audience: where the three meet

> **Developers who, after work, build their own things (apps, games, side projects) with AI coding agents, and who
> enjoy optimising systems.**

- **They can install it:** Claude Code or Codex and git are already there.
- **Their own repositories:** no employer's rules in the way.
- **The evening is their time:** "Office at work, Camp after work" ([work-and-play.md](work-and-play.md)) is how they
  already live: in the evening they build their own factory, not rest from work.
- **The score is Factorio's pleasure:** less wood per result ([the-score.md](the-score.md)).
- **Assets for their own game or app** are a plain gain: the "new builders" of the third hypothesis, with a developer's
  skills ([improve-buildings.md](improve-buildings.md) §12.4).
- **The owner is one of them,** building a game after work with Orkline: the founder is the user.

## 2a. The first user's day: the commute home (the owner, 2026-10-13)

> All day they review other people's merge requests and sit in calls with managers. On the metro home they take out
> the phone **looking forward to it**: they open what is nearly a game and switch into the maker's mood. They see what
> the orks built without them and what has a problem. At home they open the laptop and go on building their product,
> for the joy of it.

This is the scene the product is made for. What it asks of the design:

1. **The town works while the person is at work, and does not disturb them.** The working hours set in the onboarding
   ([work-and-play.md](work-and-play.md) §4) are quiet hours for the person's own project: no pushes, questions
   gathered. **So an ork must not stand all day on one question:** it assumes, marks the assumption, and goes on where
   that is safe ([ork-console.md](ork-console.md) §4); it waits only where a wrong guess costs more than a day.
2. **Opening the phone is the reward, so the first screen is "while you were away"**, in this order:
   - **what was built:** results at the Review gate, carts that moved, the score's change ([the-score.md](the-score.md));
   - **the questions,** each answerable with one tap or a line, in under a minute between two stations;
   - **the problems** (🔥, stuck carts), each with what it waits for;
   - **what it cost:** the window's % used while away ([town-time.md](town-time.md) §3).
   Wins first, so the evening starts with joy, not a list of errors. The same screen greets the laptop when it is opened.
   It is the morning brief ([cut-list.md](cut-list.md)) made for any return, not only the morning.
3. **Decided on the phone, built at home.** The phone answers, passes or sends back, and drops ideas
   ([cut-list.md](cut-list.md) §3a). Long reading and the work itself wait for the laptop. Answers given underground,
   with no signal, are kept and sent when it returns.
4. **The laptop stays on at home and the phone reaches it over Tailscale** ([mobile.md](mobile.md), already built).
   With the computer off, the mailbox for decisions ([cut-list.md](cut-list.md) §3c) is the later answer.
5. **The terms:** a person's own subscription working on their own project during the day is ordinary use; still,
   never advertised as "agents round the clock" ([decisions-2026-10.md](decisions-2026-10.md) §5).

**Where the town lives during the day** (the owner, 2026-10-13). People from large companies leave the home laptop at
home, as the owner does, **but turn it off or let it sleep**: today nothing useful happens there without them, since
their agents stop on the first question. Those working from home often leave it on with agents running in the
background. So:

- **Two groups of the same audience.** **Remote workers:** the laptop is on already, and the scene works with no change
  of habit (the commute becomes lunch, or the gap between two calls). **They are the first testers to look for.**
  **Office workers:** the scene works only if they leave the laptop running, so Orkline has to make that worth it and
  safe.
- **Why they would leave it on:** the orks no longer stop on the first question (rule 1 above). That is the product's
  own answer to "nothing happens without me".
- **"Leaving the camp" is a ritual, as in a strategy game** (P0 before the launch, with "while you were away"). In the
  morning, one press: "I'm off". The Workchief says what the orks will do until evening, which carts, and the cap
  ("up to 30 % of the window"), and asks what to take first. While carts are in work and the laptop is on power, the
  town keeps the Mac from sleeping, and lets it sleep when the work is done or the cap is reached. A closed lid still
  sleeps; this is said plainly, with "leave the lid open".
- **The mailbox for decisions** ([cut-list.md](cut-list.md) §3c) helps only to answer, not to work. It stays Later.
- **The cloud runners** (Claude Code's own sessions in the cloud, and the same at the other makers) solve "the laptop
  is off", **and they are the platform risk** of [decisions-2026-10.md](decisions-2026-10.md) §4.3: the makers already
  reach a person's sessions from the phone, the owner says with a weaker interface. Running carts in someone else's
  cloud from the town breaks local-first and may run into their terms. **Research R8, not a feature;** the story keeps
  to what the makers will not do: the town, several vendors, the cost per result.

**Short looks between work tasks** (the owner's hypothesis, 2026-10-13). To switch attention, developers open a
social feed. The camp could take that place: the pleasure of making one's own thing, in an interface made for a quick
switch. If it holds, it is the strongest habit the product can have, a few looks a day rather than one evening.

- **Pulled, never pushed.** Quiet working hours mean the town never calls; the person opening it themselves is fine.
  The rule stays.
- **A look is a break, not a second job.** A feed is passive; a list of decisions is work. So the phone opens on **the
  living camp** (orks moving, carts on the roads: a factory game's and an aquarium's pleasure) with **what changed since
  the last look** in one line ("since 40 min ago: 2 carts at the gate, 1 ❓"). One tap answers or passes; nothing must
  be done. A look lasts under a minute and a half.
- **"While you were away" becomes "since your last look":** the same screen, measured from the last look, not the last
  day. No new feature; the phone console and that screen are shaped by it.
- **Honest when nothing changed:** "nothing new since 12:40; the orks are on #42" rather than invented news.
- **No hooks of a feed:** no endless list, no streaks, no invented notifications, no red dots to clear. The person
  should leave a look glad, not pulled back. Any spend a tap starts is said on the button.
- **Checked:** phone looks a day for active testers, their median length, the share with an action; and a question to
  testers: "did it feel like a break or like work?". Aim: three or more looks a day, median under two minutes, "a
  break" from most.
- **A line for the posts, if it holds:** "Open your camp instead of the feed."

**What it changes:**

- **The story for the article and the launch post opens with this scene.** It is truer than "an evening in the camp":
  it names the pain (a day of other people's work) and the pleasure (one's own thing, waiting).
- **The GIF:** the phone on the way home (built, one ❓ answered) → the laptop at home, the same town in Camp.
- **Priority:**
  - "while you were away" is **P0 before the launch**, on the laptop first;
  - quiet working hours with questions gathered are **P0 before the launch**, with the hours asked in the onboarding;
  - the phone console moves to **the first P1**, ahead of the town's clock;
  - the mailbox for decisions stays **Later**.
  - "leaving the camp", with the Mac kept awake while carts are in work on power, is **P0 before the launch**.
- **How it is checked** (§6): for each tester, whether the town is opened on the way home or in the evening, and from
  which device; whether they work from home; whether office workers leave the laptop on after "I'm off". If testers do
  not open it away from the laptop, the phone goes back down.

## 3. The story

> **Orkline: build the factory that builds your side project — your coding agents as a town you grow after work.**

(A draft line for the README and the posts.) **Q2:** a control room for the agents that build the person's project;
automating the rest of a person's work is "and more", below the fold.

Factorio may be named in talk ("like Factorio, but the factory ships your app"), never in the name or the art: the same
care as in [open-questions.md](open-questions.md) Q18.

## 4. Later, not first

| audience | when |
|---|---|
| people in IT, at work (Office in working hours) | when a security story a company accepts exists; local-first helps |
| content creators who are not developers | when installing needs no CLI |
| the classic game development community | not aimed at |

## 4a. A second job for the same people: the routine of their own life (Later)

The owner, 2026-10-13: the same people automate their personal, not work, routine: replies to mail, registering for
events, research on personal questions (where to have the dog groomed, which vaccinations a child needs).

- **Second, not first.** One-off personal research is done well already by general assistants and their agent modes;
  a town adds little there. Orkline's edge is where things **repeat and follow rules**: replies by rules, a weekly
  look for events to register for, a vaccination plan that reminds of its dates. It stays the "and more" of §3, out of
  the GIF and the first paragraph.
- **The stakes are higher than in code:**
  - **whatever leaves the town** (a reply to a person, a registration, a form filled in a browser by the Publisher)
    cannot be taken back and may carry money: **it passes the Review gate by default**, proposed, not done, until the
    person allows it for that road in so many words;
  - **health and law:** sources always, each finding marked confirmed or disputed (the Research building already does
    this), and said plainly: "not a doctor's advice". Never given as ready advice.
- **A mission for it, Later:** "The camp at home": mail by rules and one personal errand that comes back; it teaches
  that what goes out goes through the gate ([first-mission.md](first-mission.md) §8).
- **The owner uses it so already:** a test of the gate for the outside world on the owner's own life.

## 5. What it changes

- **Mission 1's classes:** the developer with a side project is the default class; its quest 4 reads the project's
  GitHub ([first-mission.md](first-mission.md) §3).
- **The GIF:** an evening, the camp, two orks building a feature of a small game while the person answers one ❓.
- **The launch's channels:** side-project and vibe-coding communities, indie hackers, Claude Code and Codex
  communities; developers who talk about Factorio.

## 6. How it is checked

The first 10–15 testers are found in three places: Claude Code communities and working developers; side-project,
vibe-coding and indie-hacker communities; developers who say they play Factorio. For each group: Mission 1 finished,
back within 7 days, **the hours of use** (evenings and weekends, or working hours), the look chosen. The group with
the best seven-day return decides the GIF and the posts; if it is not this one, this page changes.
