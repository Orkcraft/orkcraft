# Design — open questions for the owner (2026-10-12)

Status: asked 2026-10-12, at the end of a day of product decisions ([ork-console.md](ork-console.md),
[cut-list.md](cut-list.md), [first-mission.md](first-mission.md) and the rest). Each question says why it matters and
the default the docs follow until it is answered. **Blocks P0** marks the ones the first fifteen minutes or the
launch wait on. Answers go under each question, and the doc it changes is updated with them.

## A. Who it is for and what it is

- **Q1.** **Who is the first user?** Three audiences came up today: developers running several coding agents at once; new
   builders making their first apps and games with AI; people like the owner who throw in ideas and have them talked
   through and built. The demo GIF, the first mission and the posts can serve one. **Blocks P0.**
   *Default:* developers running several Claude Code or Codex sessions at once.
  *Answered 2026-10-13:* developers who build their own things after work with AI coding agents and enjoy optimising
  systems ([audience.md](audience.md)).
- **Q2.** **A control room for coding agents, or a town that automates a person's work?** The owner uses both (code, and
   mail, meetings, research). The launch tells one story. **Blocks P0.**
   *Default:* the control room; automation is "and more" below the fold.
  *Answered 2026-10-13:* a control room for the agents that build the person's project; automating the rest of their
  work is "and more" ([audience.md](audience.md) §3).
- **Q3.** **Roads in the first fifteen minutes:** are event-driven roads the core, or an advanced layer? Quest 1 shows one.
   *Default:* one road, shown, not built by the person in the first session.

## B. Mechanics

- **Q4.** **What an Agent pool's task makes by default.** A branch and a pull request suit code; for a game's assets, docs or
   ideas they are heavy. *Default:* a branch and a pull request for code; for anything else a result on the card,
   passed at the Review gate.
- **Q5.** **Three kinds of review:** the Review gate (rules, or the person), the Review board (a clan judges), the Agent pool
   steward's own review. Should two of them become one? *Default:* keep the gate (a decision) and the board (opinions);
   the pool's own review shows as a session of its steward.
- **Q6.** **Where a new idea goes:** the Task board's Ideas, the Warchief's line, a talk ([ork-console.md](ork-console.md)
   §21). One way in or several? *Default:* everything ends as a card in Ideas; the line and a talk ask where it
   belongs.
- **Q7.** **Autonomy for a new person:** "propose only" is safe and asks often; "apply if unanswered" is calm and riskier.
   *Default:* propose only, until the ask channel (§4 of ork-console.md) makes the questions cheap.
- **Q8.** **Money or limits in the HUD?** For a person on a subscription the $ are an API-price estimate they never pay; what
   they meet is the limit. **Blocks P0** (the HUD in the GIF). *Default:* on a subscription, the window's % first and $
   on the mouse; on an API key, $.
  *Answered 2026-10-13:* on a subscription, the % of the window, not $. Which window: **the one that, at today's pace,
  runs out first** (usually the five-hour one; the weekly one when it is tighter), the other on the mouse
  ([town-time.md](town-time.md) §3).
- **Q9.** **Several AI tools:** do agy and Codex really do what Claude Code does in every building, or is Claude Code the lead
   and the others helpers? *Default:* Claude Code leads; the first mission runs on it when it is there.
- **Q10.** **The builder in the first days:** a building made from words can be weak, and a tester's first weak building is
    a bad first impression. *Default:* the builder is offered after Mission 1, not in it.

## C. Looks

- **Q11.** **The art:** are you happy with today's sprites, are all of them in one style, and which were generated? The GIF
    is judged on them, and a mixed style reads as AI slop. *Default:* the Alchemist checks the GIF's buildings for one
    style before the launch.
- **Q12.** **How much fits:** on a 13-inch laptop, how many buildings at medium size before the town is crowded? The first
    town has five ([catalog-shelves.md](catalog-shelves.md)). *Default:* the first town fits one screen at the
    overview zoom.
- **Q13.** **Office in the README:** is Office shown beside Camp (a screenshot), or only mentioned? *Default:* one line and
    one small screenshot, for the people who think it is a toy.
  *Answered 2026-10-13:* yes, both looks side by side, "At work: Office. After work: Camp. The same town."
  ([work-and-play.md](work-and-play.md) §4b).
- **Q14.** **The camp's jokes:** the Warchief's lines joke. Does that sit well with a developer who is tired at 2 a.m.? *Default:*
    jokes in growth news and the mission only; never on an error, money or a question.

## D. Install, trust, safety

- **Q15.** **Which systems are checked on a clean machine:** macOS only, or Linux and Windows too? Asked at the start of the
    day, not answered. **Blocks P0.** *Default:* macOS checked; Linux and Windows "should work", said so.
  *Answered 2026-10-13:* macOS only for now. The README says so plainly ("checked on macOS; Linux and Windows should
  work, not yet checked"); the first testers mostly on macOS, one or two on Linux to learn what breaks; the install
  check in CI on three systems stays in the launch plan.
- **Q16.** **The hooks in the person's repository:** `orkcraft hooks install` writes into `.claude/settings.json`. Does the
    first mission need them, and is it said plainly before they are written? **Blocks P0.** *Default:* asked once
    before writing, with what is written and how to take it back.
  *Answered 2026-10-13:* yes, for every AI tool: the Warder, the session log and the way to ask all stand on them.
  Asked once, **before quest 4** (the first real model call; quests 1–3 run none), showing line by line what is written
  where; into the project's settings, not the global ones, where the tool allows; reversible (`orkcraft hooks remove`
  and a button in Settings). Whether Codex and agy take hooks as Claude Code does is research R7.
- **Q17.** **`.orkcraft/` in the person's repository:** is it added to their `.gitignore` by itself? The logs hold whole
    prompts ([dogfood-logs.md](dogfood-logs.md)). *Default:* yes, by itself, and said so.

## E. Name, community, the author

- **Q18.** **The name and the look beside Warcraft.** "Orkcraft", orks, the sprite prompts saying "in the style of Warcraft
    II (1995)" ([sprites.md](sprites.md)), the Warcraft III clock. A style is not owned, but a name and a look close to
    a well-defended brand can draw a letter. Has this been weighed? **Blocks the launch**, not P0. *Default:* no
    "Warcraft" in the README, the posts or any prompt that ships; "a real-time strategy game" instead.
  *Assessed 2026-10-12* (a product view, not legal advice): found in the repository **no Blizzard art, sounds or game
  quotes**; the fonts are open (OFL: Pixelify Sans, Titillium Web, JetBrains Mono, Almendra SC); the word "Warcraft"
  in about 15 files, among them the shipped `orkcraft/design/prompts/ork.md` and the design system. **Low likelihood,
  medium impact, growing with visibility:** the realistic worst case is a polite request to rename, cheap now and
  painful after a launch. The name alone is a small risk ("-craft" is everywhere, orks are common fantasy, a free
  developer tool, not a game); a Pixel style of the 1990s is not owned; using "Warcraft" to promote would be the
  likeliest trigger. **Before the launch (about an hour):** "Warcraft" out of the shipped prompts and the design
  system ("1990s real-time strategy pixel art", checked on a few renders), and out of the README, the posts and the
  article; the design docs may keep it as history; no trademark filed for "Orkcraft"; a lawyer if money ever comes
  under the name.
  *Decided 2026-10-13:* **every mention goes from the resources, the code and the prompts.** The task, P0 before the
  launch, text only (no behaviour changes):

  | where | what |
  |---|---|
  | `orkcraft/design/prompts/ork.md` | the shipped prompt: "in the style of Warcraft II (1995)" → "in the style of a 1990s real-time strategy game"; checked on a few renders |
  | `docs/design/building-prompts.md`, `docs/design/sprites.md`, `docs/design/building-sprites.md` | the prompts written in the docs, the same way |
  | `design-system/components.css`, `design-system/components.md`, `design-system/tokens.json` | "Warcraft 2" in comments and descriptions → "1990s real-time strategy" |
  | `orkcraft/gui/static/js/portrait.js` | its first comment |
  | `docs/reference.md`, `docs/design/gui-design-system.md`, `docs/design/gui-migration.md`, `docs/design/growth.md`, `docs/design/portrait.md` | the mentions in prose |
  | the README, the posts, the article | never written |

  The docs of 2026-10-12 and -13 are already cleaned; the word stays only where it names this task. No trademark filed
  for "Orkcraft".
- **Q19.** **Buildings from the community:** is a building one folder a person can send as a pull request? Asked at the
    start of the day, not answered. *Default:* not yet; the "Build a building" guide waits for it.
- **Q20.** **The author's story:** how much of "built with the agents it runs" is to be told, and does anything (an employer,
    a contract) limit it? *Default:* told in full in the article.

## F. Research to-do (for engineering, before the P1s they feed)

Not questions for the owner: things to find out in the code and in each AI tool, each a short write-up with what was
found. Gathered from the docs of 2026-10-12 and -13.

- **R1. How an ork's session runs:** one headless call, or a live terminal; what "open the session" means for
  `claude`, `codex` and `agy` ([ork-console.md](ork-console.md) §12). Feeds P0 (the console).
- **R2. A way to ask and to mark assumptions in every AI tool**, also run without a terminal: a tool Orkcraft gives
  every ork (MCP), the tool's own question form, or a block at the end of the run ([ork-console.md](ork-console.md)
  §4, §20). Feeds P0.
- **R3. Files read and tools run, out of each AI tool's trail:** Claude Code's transcript has them; Codex's rollout
  and agy's brain folder to be checked ([cart-waybill.md](cart-waybill.md) §2). Feeds P1 (the waybill).
- **R4. A cart's id across its stops:** which entries mint one; sub-ids at a split; every id kept at a join (today
  only the first); "made from" and "born of" ([cart-waybill.md](cart-waybill.md) §5). Feeds P1.
- **R5. Each AI tool's limit windows**, where they can be read (Codex's `resetsAt`; Claude Code's and agy's)
  ([town-time.md](town-time.md) §3). Feeds P1.
- **R6. The cost of a single run in each AI tool**, for the console's history ([ork-console.md](ork-console.md) §12).
- **R7. Hooks in every AI tool:** what Codex and agy offer in place of Claude Code's hooks (before a tool runs, at a
  session's start and end), project-local or global, and how each is taken back ([agy-guard.md](agy-guard.md) for
  agy). Feeds P0 (the Warder and the way to ask in quest 5 and after).
