# Design — the product decisions of 12–13 October 2026: an index

Status: the one place to start from. Two days of product and UX decisions with the owner, spread over fifteen docs;
this page says what was decided, where, and in what order to build it. When a doc below changes a decision, this page
changes with it. The owner works on the tasks in parallel while looking for the first testers.

## 1. The model in five rules

1. **Three things, each seen one way:** an **ork** (who: a role, its runs are sessions) in its console; a **building**
   (how work flows) in its card and one Info; a **cart** (what is worked on) in its waybill.
   [ork-console.md](ork-console.md), [lighter-buildings.md](lighter-buildings.md), [cart-waybill.md](cart-waybill.md)
2. **Shown on what it is about:** a talk on its card, an improvement beside its result, a wait on what waits.
3. **Calm by default, full control on demand:** the town lifts the person only for a question or an error; any
   session can be opened.
4. **The game's score is wood and limit per accepted result**, guarded by quality. [the-score.md](the-score.md)
5. **One expertise, one ork; the cheapest thing that works.** [town-hall-roles.md](town-hall-roles.md)

## 2. The docs

| doc | what it decides |
|---|---|
| [audience.md](audience.md) | **who it is for first**: developers building their own things after work with AI agents, who enjoy optimising systems |
| [ork-console.md](ork-console.md) | orks, sessions, buildings; ask / assume and mark / decide; one status; the console; 🥩 list; waits that say why (§19); answers read questions first (§20); talks on their cards (§21); **the priority table (§11)** |
| [lighter-buildings.md](lighter-buildings.md) | no Work panel: a card, a command card, one Info; setup of one question |
| [cart-waybill.md](cart-waybill.md) | a cart's waybill in the Inspector; one id for life, sub-ids at a split; the Review gate as the place of judgement |
| [the-score.md](the-score.md) | the score per result; the audit's free rules often; one 💡 list, and the item beside its result |
| [first-mission.md](first-mission.md) | the first session as Mission 1: a drill cart, real read-only work, two orks at once |
| [catalog-shelves.md](catalog-shelves.md) | the core shelf, plumbing, More, Improve tools; Metrics as an outside source's chart; Branches & PRs is manual git |
| [cut-list.md](cut-list.md) | what is hidden, frozen, merged, dropped; the night off by default; the phone as the console |
| [town-hall-roles.md](town-hall-roles.md) | eleven names to eight; the Elders are a Town Hall flow |
| [town-time.md](town-time.md) | every schedule on the sun and moon dial; work held for a limit's reset |
| [connections.md](connections.md) | MCP first, a token later, offered with what it saves |
| [ork-icons.md](ork-icons.md) | an ork's face says its role |
| [color-pass.md](color-pass.md) | quiet ground, clear buildings, loud signals; the yard as ground with a light fence; pixels stay |
| [work-and-play.md](work-and-play.md) | Office at work, Camp as the game after work; one layout, two drawings (numbers ↔ things) |
| [dogfood-logs.md](dogfood-logs.md) | what is logged; what to switch on before the owner's game; what is missing |
| [improve-buildings.md](improve-buildings.md) §12.4 | the benches beyond Orkcraft: Later, with a gate; assets offered to new builders, not the classic game dev community |
| [open-questions.md](open-questions.md) | the owner's open questions (Q1–Q20) and the research to-do (R1–R6) |

## 3. The order of work

**P0 now** (worth having for the first three testers):

1. the log check of 10–15 of the owner's sessions, no code ([ork-console.md](ork-console.md) §1a); it sizes item 2;
2. a way to ask and to mark assumptions, Claude Code first, its questions pinned on top (§4, §20);
3. one status with waits that say why and an ork's cart named (§5, §19; [cart-waybill.md](cart-waybill.md) §4);
4. the 🥩 list with 🔥 · ❓ and Stop all (§8); the console, folded (§7);
5. the night's work off in a new town; External listeners offer GitHub, a schedule, a webhook, a file ([cut-list.md](cut-list.md));
6. the colour pass by tokens, forest biome only ([color-pass.md](color-pass.md) §3);
7. Mission 1, quests 1–3: the person raises the Task board, the Agent pool and the Review gate and meets each
   ([first-mission.md](first-mission.md) §3).

**P0 before the launch:** the console unfolded; the removals it replaces; the Agent pool's lanes as roles; the local
event log and its events; quests 4–5; the onboarding cut; "Warcraft" out of what ships and is posted
([open-questions.md](open-questions.md) Q18); the README's first screen without the phone; Camp at the map and overview zooms as a living town with no cards
([work-and-play.md](work-and-play.md)); Camp committed to the game: a reference frame and a new palette for the five core
buildings ([color-pass.md](color-pass.md) §8).

**P1, first:** the town's clock and held work ([town-time.md](town-time.md)); a cart's id, its waybill and its origin
([cart-waybill.md](cart-waybill.md) §2a); the phone
as the console with assets on cards; Work gone type by type; the Town Hall's roles folded, then ork faces; the score
and the 💡 list; the yard as ground; each biome's palette.

**Later:** the campaign after Mission 1: a process that comes back, the wiki, debating agents, a script in an
agent's place, a building of one's own, each offered when its moment comes ([first-mission.md](first-mission.md) §7–8); a cart's price on the roads beyond the waybill; the benches beyond Orkcraft; packs by kind of user; search
across talks; a light theme.

**No:** the town moved to a cloud backend (a mailbox for decisions instead, Later: [cut-list.md](cut-list.md) §3c); a
native phone app until a measured blocker; a hidden Town Hall feature for the person's own project; the window as a big building; isometry; a painted
style; the phone's places; Sound alerts as a building.
