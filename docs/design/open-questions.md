# Design — open questions for the owner (2026-10-12)

Status: asked 2026-10-12, at the end of a day of product decisions ([ork-console.md](ork-console.md),
[cut-list.md](cut-list.md), [first-mission.md](first-mission.md) and the rest). Each question says why it matters and
the default the docs follow until it is answered. **Blocks P0** marks the ones the first fifteen minutes or the
launch wait on. Answers go under each question, and the doc it changes is updated with them.

## A. Who it is for and what it is

1. **Who is the first user?** Three audiences came up today: developers running several coding agents at once; new
   builders making their first apps and games with AI; people like the owner who throw in ideas and have them talked
   through and built. The demo GIF, the first mission and the posts can serve one. **Blocks P0.**
   *Default:* developers running several Claude Code or Codex sessions at once.
2. **A control room for coding agents, or a town that automates a person's work?** The owner uses both (code, and
   mail, meetings, research). The launch tells one story. **Blocks P0.**
   *Default:* the control room; automation is "and more" below the fold.
3. **Roads in the first fifteen minutes:** are event-driven roads the core, or an advanced layer? Quest 1 shows one.
   *Default:* one road, shown, not built by the person in the first session.

## B. Mechanics

4. **What an Agent pool's task makes by default.** A branch and a pull request suit code; for a game's assets, docs or
   ideas they are heavy. *Default:* a branch and a pull request for code; for anything else a result on the card,
   passed at the Review gate.
5. **Three kinds of review:** the Review gate (rules, or the person), the Review board (a clan judges), the Agent pool
   steward's own review. Should two of them become one? *Default:* keep the gate (a decision) and the board (opinions);
   the pool's own review shows as a session of its steward.
6. **Where a new idea goes:** the Task board's Ideas, the Warchief's line, a talk ([ork-console.md](ork-console.md)
   §21). One way in or several? *Default:* everything ends as a card in Ideas; the line and a talk ask where it
   belongs.
7. **Autonomy for a new person:** "propose only" is safe and asks often; "apply if unanswered" is calm and riskier.
   *Default:* propose only, until the ask channel (§4 of ork-console.md) makes the questions cheap.
8. **Money or limits in the HUD?** For a person on a subscription the $ are an API-price estimate they never pay; what
   they meet is the limit. **Blocks P0** (the HUD in the GIF). *Default:* on a subscription, the window's % first and $
   on the mouse; on an API key, $.
9. **Several AI tools:** do agy and Codex really do what Claude Code does in every building, or is Claude Code the lead
   and the others helpers? *Default:* Claude Code leads; the first mission runs on it when it is there.
10. **The builder in the first days:** a building made from words can be weak, and a tester's first weak building is
    a bad first impression. *Default:* the builder is offered after Mission 1, not in it.

## C. Looks

11. **The art:** are you happy with today's sprites, are all of them in one style, and which were generated? The GIF
    is judged on them, and a mixed style reads as AI slop. *Default:* the Alchemist checks the GIF's buildings for one
    style before the launch.
12. **How much fits:** on a 13-inch laptop, how many buildings at medium size before the town is crowded? The first
    town has five ([catalog-shelves.md](catalog-shelves.md)). *Default:* the first town fits one screen at the
    overview zoom.
13. **Office in the README:** is Office shown beside Camp (a screenshot), or only mentioned? *Default:* one line and
    one small screenshot, for the people who think it is a toy.
14. **The camp's jokes:** the Warchief's lines joke. Does that sit well with a developer who is tired at 2 a.m.? *Default:*
    jokes in growth news and the mission only; never on an error, money or a question.

## D. Install, trust, safety

15. **Which systems are checked on a clean machine:** macOS only, or Linux and Windows too? Asked at the start of the
    day, not answered. **Blocks P0.** *Default:* macOS checked; Linux and Windows "should work", said so.
16. **The hooks in the person's repository:** `orkcraft hooks install` writes into `.claude/settings.json`. Does the
    first mission need them, and is it said plainly before they are written? **Blocks P0.** *Default:* asked once
    before writing, with what is written and how to take it back.
17. **`.orkcraft/` in the person's repository:** is it added to their `.gitignore` by itself? The logs hold whole
    prompts ([dogfood-logs.md](dogfood-logs.md)). *Default:* yes, by itself, and said so.

## E. Name, community, the author

18. **The name and the look beside Warcraft.** "Orkcraft", orks, the sprite prompts saying "in the style of Warcraft
    II (1995)" ([sprites.md](sprites.md)), the Warcraft III clock. A style is not owned, but a name and a look close to
    a well-defended brand can draw a letter. Has this been weighed? **Blocks the launch**, not P0. *Default:* no
    "Warcraft" in the README, the posts or any prompt that ships; "a real-time strategy game" instead.
19. **Buildings from the community:** is a building one folder a person can send as a pull request? Asked at the
    start of the day, not answered. *Default:* not yet; the "Build a building" guide waits for it.
20. **The author's story:** how much of "built with the agents it runs" is to be told, and does anything (an employer,
    a contract) limit it? *Default:* told in full in the article.
