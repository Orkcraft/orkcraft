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
| [color-pass.md](color-pass.md) | quiet ground, clear buildings, loud signals; **the card is the building: a roof that lifts as you zoom in** (§6a); pixels stay; the art that ships is made by people (§10) |
| [town-readability.md](town-readability.md) | carts, orks and their link readable on a bright camp: outlines, reserved signal colours, badges only for exceptions, a spotlight on hover |
| [work-and-play.md](work-and-play.md) | Office at work, Camp as the game after work; one layout, two drawings (numbers ↔ things) |
| [dogfood-logs.md](dogfood-logs.md) | what is logged; what to switch on before the owner's game; what is missing |
| [improve-buildings.md](improve-buildings.md) §12.4 | the benches beyond Orkcraft: Later, with a gate; assets offered to new builders, not the classic game dev community |
| [backlog.md](backlog.md) | **the development backlog to the launch**: items with ids, lanes that run in parallel, dependencies, days |
| [camp-story.md](camp-story.md) | the camp's story: work comes in at the ways in, is refined on the line, and is catapulted over the wall; the GIF ends on a launch; "launched" in the score |
| [v3-prompts.md](v3-prompts.md) | **v3**: prompts for the reference frames (town, a building clicked, an ork clicked, the Task board inside, a cart's history) and every asset to replace (§13) |
| [asset-prompts.md](asset-prompts.md) | prompts for reference sprite sheets: the ork body and roles, carts, ground and roads, the building kits, facades and crests |
| [design-system-v2.md](design-system-v2.md) | **the design system for the new Camp**: the grid and scale ladder, one projection, the layers, the cover kits, track, carts and orks with their slots, signals and chips, the world palette as tokens, the sprite pipeline; its open questions; and [artist-brief.md](artist-brief.md), the commissioned artist's brief made from it |
| [naming.md](naming.md) | name candidates should Orkcraft be renamed (Q18): criteria, twelve names, the first three, the checks |
| [distribution.md](distribution.md) | the doors where the audience installs: PyPI and a Claude Code plugin before the launch, a VS Code and Open VSX extension after the testers; a door, never a second face |
| [launch-prep.md](launch-prep.md) | the week's goal by 18 October; GitHub, the landing page and the materials prepared for the marketing from 19 October |
| [similar-products.md](similar-products.md) | the projects that show agents as characters in a game world (Pixel Agents and others): the category's ticket, not our difference; we run the work, they watch sessions |
| [open-questions.md](open-questions.md) | the owner's open questions (Q1–Q22) and the research to-do (R1–R10) |

## 3. The order of work

**The calendar (the owner, 2026-10-13; moved 2026-10-15, §15: no date, the launch is the owner's "ready"):** until the end of the week of 12 October, the backlog's tasks; from 19 October,
marketing and community work starts (posts, a devlog, finding testers), in parallel with the work. **This week's
goal** and the preparation started now (materials, the landing page, GitHub for search): [launch-prep.md](launch-prep.md).

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
buildings ([color-pass.md](color-pass.md) §8); the "while you were away" screen, quiet working hours with
questions gathered, and "leaving the camp" with the Mac kept awake while carts are in work
([audience.md](audience.md) §2a, the commute home; the first testers among remote workers); Orkcraft on PyPI and
a Claude Code plugin ([distribution.md](distribution.md)); the art the GIF and the landing show made by people (a CC0
pack and a commissioned pixel artist), generated images only as references ([color-pass.md](color-pass.md) §10); **the card is the building** for the five
core buildings: a cover (roof, open scene, or tower and gate) that lifts close up, a facade and a crest, the signals on
the cover, a sheet from the bottom on the phone ([color-pass.md](color-pass.md) §6a–6c); outlines, reserved signal
colours, a cart's load and flag ([town-readability.md](town-readability.md)).

**P1, first:** the phone as the console (the commute home, [audience.md](audience.md) §2a); the town's clock and held work ([town-time.md](town-time.md)); a cart's id, its waybill and its origin
([cart-waybill.md](cart-waybill.md) §2a); assets on cards on the phone; Work gone type by type; the Town Hall's roles folded, then ork faces; the score
and the 💡 list; the yard as ground round the walls; each biome's palette; a VS Code and Open VSX extension ([distribution.md](distribution.md)).

**Later:** the campaign after Mission 1: a process that comes back, the wiki, debating agents, a script in an
agent's place, a building of one's own, each offered when its moment comes ([first-mission.md](first-mission.md) §7–8); a cart's price on the roads beyond the waybill; the benches beyond Orkcraft; packs by kind of user; search
across talks; a light theme.

**No:** the town moved to a cloud backend (a mailbox for decisions instead, Later: [cut-list.md](cut-list.md) §3c); a
native phone app until a measured blocker; a hidden Town Hall feature for the person's own project; the window as a big building; isometry; a painted
style; the phone's places; Sound alerts as a building.

## 4. The risks the concept does not answer (2026-10-13)

The concept holds together; these four are not about features, and each could undo it.

1. **It has been checked on one person.** The audience, Camp after work, the campaign and the score are a stack of
   hypotheses, each standing on the one before. **A time box:** the first three testers within two weeks, whatever
   state the product is in; and the log check of [ork-console.md](ork-console.md) §1a done before that.
2. **A wrapper over three fast-moving CLIs.** Claude Code, Codex and agy change often (hooks, transcript formats, how
   limits are read); for one person that is endless upkeep. **Claude Code first, the others best-effort**
   ([open-questions.md](open-questions.md) Q9), and each adapter checked by tests against named versions, as the Codex
   limits already are ([codex-limits.md](codex-limits.md)).
3. **The platforms.** The makers of the AI tools are building their own views of parallel agents; if one shows "who is
   waiting for you" well, the plain control room loses its worth. The story stands on what they will not do: the town
   and the game, several vendors at once, local-first, the cost per result, roads between buildings
   ([audience.md](audience.md) §3). **From below as well:** open-source views of agents as pixel characters, one with
   ~10k stars, plan to add a game layer and orkestration ([similar-products.md](similar-products.md)).
4. **The way for the community is undecided**, and community is one of the owner's two goals: whether a building or a
   mission can be one folder sent as a pull request ([open-questions.md](open-questions.md) Q19).

**The owner's answers (2026-10-13):**

1. The risk is known; the design of the system and the product's goal are finished. At worst it is a game for the
   owner.
2. The owner keeps three subscriptions (Claude, ChatGPT, Gemini) to keep all three tools working.
3. The platforms: the story stands on what they will not do.
4. **The community is built before the launch, as indie games do it:** as close to the people as possible. It is the
   only way to popularity and recognition. Q19 (a building or a mission as one folder sent as a pull request) is
   answered before the launch.

## 5. The AI tools' terms, checked 2026-10-13 (not legal advice)

| tool | what was found | what follows |
|---|---|---|
| **Claude Code** | Anthropic's [Legal and compliance](https://code.claude.com/docs/en/legal-and-compliance): third parties may not offer Claude.ai login, route requests through a person's subscription, or collect or store session tokens; **a person signing in to the unmodified Claude Code binary with their own subscription is allowed**. Pro and Max limits "assume ordinary, individual usage". Orkcraft runs the person's own `claude`, sign-in is Anthropic's own, limits are read through the CLI; no token handling found in the code | **allowed.** Keep the night's work off by default ([cut-list.md](cut-list.md)); never advertise many agents running round the clock on a subscription |
| **agy** | Google banned accounts in February 2026 for "use of 3rd party tools or proxies to access Antigravity resources and quotas"; the ban reached Gemini CLI too; a second flag is permanent ([gemini-cli discussion 20632](https://github.com/google-gemini/gemini-cli/discussions/20632)). Piggybacking on its OAuth is forbidden; Orkcraft runs the official `agy`, it does not take its tokens. Secondary sources report Google's FAQ calling the wrapping of agy in third-party apps unsupported on consumer plans, with an API key advised; **not confirmed first-hand** (Google's site was unreachable from here) | **the highest risk, and to the owner's own Google account.** Until the owner reads Google's [FAQ](https://antigravity.google/docs/faq/) and [terms](https://antigravity.google/terms/): agy marked experimental and at the person's own risk, never on by default, with a plain warning of a possible account ban; out of the launch's story; a Gemini API key offered instead |
| **Codex** | OpenAI documents signing in to the Codex CLI with a ChatGPT plan ([help](https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan)); `codex exec` is its own non-interactive mode. No rule found either forbidding or allowing another program to run the person's own CLI | **likely fine, not confirmed:** read OpenAI's current Terms of Use once |
| **Cursor** (limits only) | `orkcraft/quota/cursor_quota.py` reads Cursor's stored login token from its `auth.json` and calls an undocumented API with it: in spirit what Anthropic and Google forbid | **P0 before the launch:** removed, or kept only behind an explicit opt-in that says what it does |

So: **Claude Code is the main tool** (it matches §4.2's "Claude Code first"); Codex beside it once its terms are read;
agy experimental until Google's own words are read.

## 6. Decided on 13 October, in short

| decision | where |
|---|---|
| Camp's direction: round 2's orkish camp, grass a step quieter in two or three tones, banners maroon, the palisade only on the camp's edge | [color-pass.md](color-pass.md) §9c |
| the frame must say *code*: two or three developer tells and a visible chain of carts | [color-pass.md](color-pass.md) §9b |
| carts, orks and their link read on a bright camp: outlines and shadows, yellow and red only for signals, work as motion, words on chips, the link by place and a spotlight | [town-readability.md](town-readability.md) |
| **the card is the building:** its cover lifts close up; two marks (facade, crest); three kinds (hall, open ground, tower or gate); on the phone a sheet from the bottom | [color-pass.md](color-pass.md) §6a–6c |
| the art that ships is made by people: a CC0 pack and a commissioned pixel artist under CC-BY 4.0, asked this week; generated art for the testers and the devlog, said so; ≈ $1.5–4k, the launch's minimum ≈ $0.7–1.8k | [color-pass.md](color-pass.md) §10–10b |
| a pack is chosen by its licence first: Minifantasy's forbids a public repository | [color-pass.md](color-pass.md) §10a |
| the first user's day: the commute home, "since your last look", short looks instead of a feed, the town working while away, "leaving the camp"; the first testers among remote workers | [audience.md](audience.md) §2a |
| the category exists (Pixel Agents ~9.7k stars, 126k installs, 155 in its Discord): demand proven, go fast, learn but differ — "they show your agents, Orkcraft runs the work" | [similar-products.md](similar-products.md) |
| the doors where the audience installs: PyPI and a Claude Code plugin before the launch, a VS Code and Open VSX extension after the testers | [distribution.md](distribution.md) |
| the name: Warcraft's look is the likelier risk than Games Workshop's (no "Ork" word mark found); a small disclaimer; Camp's UI off gold; a register search and a plan B before the name is locked in this week | [open-questions.md](open-questions.md) Q18 |
| the week's goal by 18 October, marketing from 19 October; one home for talk (Discord and Discussions), automated broadcasting through the town's Review gate, communities by hand; the first month measured in people | [launch-prep.md](launch-prep.md) |

## 7. To test tomorrow (14 October)

1. **The reference sprite sheets** of [asset-prompts.md](asset-prompts.md), and **the reference images** of [color-pass.md](color-pass.md) §9d, add **a frame of the card as a building**: one
   hall, one open ground (the Review board's fire), one gate, each with its facade and crest, at the overview zoom and
   with the cover half-lifted; and **a phone frame** with a card's sheet open.
2. **Checked on each:** the grey test, squinting, five seconds ("which ork waits for you, which cart is stuck,
   which building is which?") ([town-readability.md](town-readability.md) §6).
3. **Minifantasy's ork at the overview zoom:** do ❓, `!` and a cart's load still read on it
   ([color-pass.md](color-pass.md) §10a).
4. **The licence on the Orc Kingdom page**, read by the owner; then the letter to the artist.
5. **The name:** ORKCRAFT is free in the registers, but Microsoft's "-craft" family reaches class 42; nothing locks the
   name in (PyPI, plugin, Discord, posts) until a lawyer's hour this week; name candidates with neither "ork" nor
   "-craft" checked in parallel; **decided by Friday 17 October** ([open-questions.md](open-questions.md) Q18).

## 8. Development starts here (from 14 October)

Everything the week's code needs is decided; the name waits (nothing that locks it in is built this week). In order:

1. **The owner's log check** of 10–15 sessions ([ork-console.md](ork-console.md) §1a), no code, 1–2 hours: it sizes
   step 3.
   **Without the logs** (the owner, 2026-10-13: they may not be at hand): step 3 goes on with the docs' defaults, at its
   smallest (Claude Code only; a pinned question; an assumption marked in a block at the run's end), and **counts
   itself**: questions asked, assumptions marked, answers given, runs that stopped on a question, into the local event
   log ([dogfood-logs.md](dogfood-logs.md)). After a week of the owner's own use, those counts do the log check's job
   and size what comes next.
2. **The small ones, about a day:** Cursor's token reader out or behind an opt-in (§5); "Warcraft" out of the shipped
   prompts and the design system (Q18 table); the night's work off in a new town and External listeners limited
   ([cut-list.md](cut-list.md)).
3. **The way to ask, Claude Code first:** research R2 first (the tool's own question form, an MCP tool, or a block at
   the run's end), then questions pinned on top ([ork-console.md](ork-console.md) §4, §20).
4. **One status with the ork's cart named** ([ork-console.md](ork-console.md) §5, §19; [cart-waybill.md](cart-waybill.md) §4).

Then, next week beside the marketing: Mission 1 quests 1–3, the colour pass (Camp's UI off gold, Q18), the console.
The goal and its dates: [launch-prep.md](launch-prep.md) §1. The critical tests of CLAUDE.md gate each merge.

## 9. Phase 1 of development, started 14 October in parallel sessions

The product is renamed **Orkline** ([naming.md](naming.md) §9). Four sessions run at once, each on its own branch,
each merging into `main` when the critical tests pass (CLAUDE.md), rebasing on `main` before every push:

| session | backlog items ([backlog.md](backlog.md)) | touches |
|---|---|---|
| 1. The name | the rename to Orkline (text only, `orkline` command beside `orkcraft`); B2 "Warcraft" out of the shipped prompts and the docs (not the design system) | README, docs, GUI strings, CLI help, `pyproject.toml` |
| 2. Small fixes | B1 Cursor's token reader; B3 the night off by default; B4 External listeners limited; B5 agy experimental and off | `quota/`, settings defaults, listeners' catalog, AI tools' setup |
| 3. Asking | A0 the local event log; A1 research R2; A2 the way to ask, Claude Code first; then A3 one status | `core/`, `realm/`, `hooks/`, the console's views |
| 4. Camp's colour | C1 the colour pass by tokens, forest only, Camp's UI off gold; B2's design-system part | `design-system/`, `gui/static/*.css` |

Sessions 1 and 4 both touch text and tokens: session 1 leaves `design-system/` to session 4.


## 10. Phase 1 done, phase 2 started (14 October)

**Phase 1 on `main`:** the rename to Orkline; B1–B5; A0–A3; C1 (Camp off gold). Critical tests green; the full suite
has two failures that predate phase 1 or are order-dependent (given to lane B).

**Phase 2, in the same four sessions** (they keep their context), beside the design-system v2 session:

| session | items |
|---|---|
| A. Asking | A4 the 🥩 list, Stop all, the console folded |
| B. Small fixes | agy out of the Test bench's defaults; the two failing tests; B6 the onboarding cut (B7 Mission 1 after A4) |
| C. Colour | C2 readability (outlines, signal colours reserved, badges for exceptions, a chip on a waiting cart), tokens additive beside design-system v2 |
| D. Name | D3 the README's first screen and `docs/github-profile.md`; the switch to orkline.dev listed, not done, until the domain serves the files |

**Widened the same day** (the owner: as many parallel sessions as possible), four new sessions:

| session | items |
|---|---|
| W1 | "since your last look": wins first, then questions, problems, cost |
| W2+W3 | quiet working hours; leaving the camp, the Mac kept awake only while carts work |
| A6 | the Agent pool's lanes as roles |
| D4 | a draft of the landing page for orkline.dev, not deployed |

Nine sessions in all with design-system v2. Waiting: B7 Mission 1 (after A4), C3 the card as a building (after
design-system v2), C4 rails, D1 PyPI and D2 the plugin (after the domain and the PyPI name).

## 11. Phase 3 started (14 October, afternoon)

Phase 2 on `main`: A4, A6, W1, W2, W3, D3, D4, design-system v2 with the artist's brief. Still running: C2, lane B
(B6, then B7 Mission 1). The owner answered design-system v2's eight questions ([design-system-v2.md](design-system-v2.md)
§12). New sessions: **C3** the card as a building, **C4** rails and mine carts, **A5** the console unfolded, **S** the
0.3 sheets moved out of the package and cut into placeholder sprites by the v2 pipeline (and `alert` re-pointed to
the question's yellow). Next after them: C5 the catapult, D5 the GIF, B8 quests 4–5.


## 12. Where things stand (14 October, evening): the handoff

**Built and on `main` today:** the rename to Orkline; B1–B8 (Cursor's token reader out, night off, listeners limited,
agy experimental, the onboarding cut, Mission 1 quests 1–5 with the hooks asked once); A0–A6 (event log, the way to
ask, one status, the 🥩 list and Stop all, the console unfolded and Work removed from the core buildings, the pool's
lanes as roles); W1–W3 (since your last look, quiet hours, leaving the camp); C1–C4 (Camp off gold, readability and
motion tokens, the card as a building for the five core buildings, rails and mine carts on a 32 px grid); the design
system v2 and the artist's brief; placeholder sprites cut from the owner's sheets; ork faces by role; the phone as the
console; D1+D2 built, not published; D3 README and GitHub profile; D4 landing draft; the marketing materials
(`docs/marketing/`).

**Known gaps, seen on the demo's screenshots:** the other buildings still in the old style beside the new covers;
Camp's ground dark instead of v2's mid-value forest; the Agent pool's canvas cover reads as a red block; the open 🥩
list draws under the cards (A5); three browser tests red since the morning (test stabilisation paused on its branch);
three face pairs to redraw (Quartermaster/Warder, Treasurer/Mechanic, Loader/Pathfinder); the per-ork `!` and ⏳
states (session running).

**Waiting on the owner:** the GitHub organisation renamed to `orkline` and the update URLs switched with a release;
orkline.dev serving `install.sh` and `updates.json`; the PyPI name and trusted publisher (`docs/distribution-howto.md`);
the five-second test on developers; the letter to the artist; Google's and OpenAI's terms; Discord and the first
devlog post from 19 October; the release 0.3.0 "Orkline".

**Next, by the backlog:** C5 the catapult and the ways in; the old buildings onto the v2 kit; the ground; D5 the GIF;
then the first three testers.


## 13. The owner's review of the day (14 October, night): the keeper instead of the cover, the inside of a building, a brighter Camp

The owner looked at the day's Camp and decided. Each line below changes what it names; the docs it names are
brought in line by the sessions that build it.

**1. The cover that lifts (C3) did not work. Replaced by the keeper** ([color-pass.md](color-pass.md) §6a–6c is
superseded here):

- **Hover** on a building (desktop): its keeper ork steps out; over its head a thought bubble with its task (the type
  and the task's name in 2–3 words); over the building a small scroll with the building's status in one or two lines
  (what the minimal cards said).
- **Click** (desktop): the scroll grows, and **quick actions** appear at the bottom for that building. On the phone,
  the first tap does what hover and click do together.
- **A second click** (the second tap on the phone) **enters the building** (below).
- **No combined menu of a building and an ork.** A click on an ork opens **its terminal** at the bottom, with tabs of
  its history (tokens, its task) — the console of [ork-console.md](ork-console.md). A click on an ork's **bubble** or
  on a **cart** opens **the task's history**: where it stopped, the tokens it spent, the stations it passed — the
  minimal waybill of [cart-waybill.md](cart-waybill.md), pulled from P1 into P0 for this.

**2. The inside of a building replaces A5's large card** ([lighter-buildings.md](lighter-buildings.md) §7 is
superseded for the view, not for the removals):

- A screen of its own. **Left:** the building from inside, scrollable when large; its orks work there, walking, their
  task in a bubble over them, tools in hand. **Right:** the building's settings as a panel in the manner of a
  merchant's window in an action RPG; settings keep plain words (CLAUDE.md). An **Exit** always visible.
- **The Task board first:** cards as large sheets of parchment or stone, to-do's checkbox as a flag. The other core
  buildings get the same layout with a plainer room until their interiors are drawn.
- Settings drawn *into* the room instead of the panel: **No** for now (plain words where money and safety are).

**3. A brighter Camp, all old assets replaced.** Brighter and more saturated **than Camp on `main` today**, away from
the strategy-game colours; every old sprite (buildings, orks, menu items, the biomes' backgrounds), the text sizes and
the fonts redone for one style. **Scale from "at most ten buildings on the screen".** A cart must be found and
recognised from far away (checked by the five-second test). **Yellow and red stay reserved for signals**
([town-readability.md](town-readability.md)); the grey test still passes. This is design system **v3**, built on v2's
grid and pipeline.

**4. The art stays generated until the product proves itself.** The owner goes to an artist only once the product is
ready and worth it. So the commission (O3, C6) moves to **Later**; [color-pass.md](color-pass.md) §10's "the art that
ships is made by people" is suspended; generated art is shown as **a concept** in posts, said so (as before). Q18's
care still holds: nothing in the art imitates the big strategy game.

**The priorities after this review:**

| id | item | priority | runs |
|---|---|---|---|
| S9 | stabilisation: the browser tests and the full suite green; no new features | **P0 now** | ∥ |
| E1 | a clean install to the end of Mission 1, on a fresh machine; a list of what breaks, fixed | **P0 now** | ∥ |
| I1 | the keeper, the bubble, the scroll and quick actions; the ork's terminal; the task's history on a bubble or cart; the cover (C3) taken out | **P0** | ∥ |
| I2 | the inside of a building replacing A5's card; the Task board drawn first | **P0** | ∥ with I1, entering through I1's second click |
| V3 | design system v3: a reference frame first (approved by the owner), then the tokens, scale, fonts, and generated sheets for every old asset | **P0** | ∥; I1 and I2 draw with v2 until it lands |
| C5 | the catapult and the ways in | Later | — |
| O3, C6 | the artist's commission | Later | after the product proves itself |

Then: the GIF (D5) on V3's art, without the catapult; the first three testers. **No** new features until their
feedback, besides these.

**The owner's answers to the review (14 October, night):**

1. **No testers until the owner finds the product ready.** The owner builds Orkline for themselves whatever testers
   would say; §4.1's time box is dropped. The hypothesis kept: **the product is first about its look** — it must
   switch a person from work mode to play mode at once.
2. The owner has not been satisfied with the look; it is brought to a finished state before anything else is shown.
3. **The name Orkline is final.**
4. Q19 (a building as one folder sent as a pull request): **after the testers.**
5. **The score is raised to P0**, at its smallest: the cost of an accepted result on the Review gate, with better or
   worse than last week.
6. The inside of a building: **the Task board only**; the others stay as they are until the owner has felt it.
7. **V3's reference frame first**, approved by the owner; I1 and I2 are built on it, not drawn twice.
8. The owner generates the images; the sessions write the prompts, the tokens and the cutting.
9. S9 and E1 wait; the new look comes first.

The prompts for the frames and for every asset to replace: [v3-prompts.md](v3-prompts.md).


## 14. Overnight, 14–15 October: the owner delegated to the PM session

### Morning summary (01:10, 15 October): what's done and what needs the owner

**Built tonight, all on `main`, full suite green (2150 passed, twice in a row at `-n auto`):**
- **The real Camp on v3 (I1).**
  - The town in F1's look: one line per row joined into a loop, and the stations (the dispatcher's booth with its
    siding, the barrier and weighbridge, the mine).
  - The steward at the stop, carts that face their travel, the score in the HUD, zoom by whole steps and pan.
  - **The phone**: Camp v3 at 390/430 px, with pan and pinch by whole steps, a bottom sheet for an ork's console, a
    cart's waybill, and one HUD line. Screens: `img/i1/phone-*`.
- **The Task board's inside (I2)**: three boards of parchment and stone cards, drag between boards, and orks
  walking inside. It uses stand-in art until GEN's run.
- **Growth and inventory (INV)**:
  - portrait stages that open by missions, lean weeks and building levels (teal eyes at stage 4);
  - building levels I–III shown as footing and banner;
  - items earned quietly and placed on grass on a grid, saved in the town file and hidden in Office. An item a new
    building displaces goes back to the inventory.
- **Mission 1 on the stations (M1)**:
  - The drill cart stands on the siding, and the person lifts the barrier.
  - The finale: the drill rolls off the weighbridge, and the Publisher launches it if there is one.
  - A deed per quest; finishing the mission opens stage 2 and earns the first-cart item. Screens: `img/m1/`.
- **Stabilisation (S9)**: the root causes behind the red tests, five of them product bugs:
  - a phone command sent twice;
  - `openBuilding` racing its module;
  - the bench feed dropping its last decision;
  - the portrait menu overflowing;
  - browser tests leaking an orkspace (the loot-cart flake).

  Nothing was skipped or quarantined. Also fixed: the quest log no longer covers the camp's bottom line (the camp
  insets above it; `img/i1/quest-log-inset.png`).
- **Mission 1b "Proof before the gate"** is designed only (first-mission.md §10, about 5 days of work). Building it
  waits until you have played Mission 1.

**Needs you (in order):**
1. **Play Mission 1 on Camp v3** on the desktop (the phone app has no quest log; look at the phone separately) and say how it feels. That decides 1b and the next missions.
2. **GEN's run, which spends Gemini credits** — say yes or no:
   `python tools/gen_sheets.py u6-inside u6-cards u2-panels -n 3 --max-calls 9` (the inside, the cards, the panels).
3. **Confirm my overnight calls:**
   - homes #1;
   - Camp's rows taken from Office positions;
   - Office and the phone keep the large Task board card;
   - for 1b: a linter as the check when a project has no tests; a narrower command for a slow suite; a flaky test or
     a red `main` never triggers 1b.
4. **Art still missing:**
   - the track junction (one 64-px tile with exits N/E/S);
   - a front view of the cart;
   - v3 art for the portrait stages;
   - art for the earned items.
5. **Rotate the Gemini key** you pasted into chat yesterday, if you haven't already.

**Session state:** all idle. I1, M1, INV and V3 are done; I2 waits for art; GEN waits for your yes. Overnight
check-ins have stopped.

### Overnight log

The owner, going to sleep: run everything in order, decide as needed, talk in the morning; GEN and V3 must not need
the owner's input. What runs, in order:

| session | does | picks |
|---|---|---|
| GEN | cuts the six picks of round 9; a fourth run: the person's homes by kin (k2), the track pieces at c2's gauge | round 4 picked by the PM session by stated rules, written in v3-prompts.md for the owner to change |
| V3 | wires the stations (dispatcher's booth and siding, the barrier and weighbridge, the mine), the Prospector, the class figures, the homes, the growth marks into the preview; writes design-system-v3.md's final state | — |
| I1 | brings the real Camp onto v3: the town drawn in v3 (the line per row, the loop, the stations, zoom and pan), the steward and the scroll and quick actions, the ork's terminal and the cart's history, the score made visible, the growth marks | — |

Next, after I1: I2 (the Task board's inside — now the dispatcher's booth inside), then the inventory and the portrait's
growth (v3-prompts §14), then Mission 1 on the stations and mission 1b (first-mission.md §9).

**For the morning (PM notes):**

- **The Gemini key's credits are spent.** GEN's fourth run (the homes by kin, the track pieces at c2's gauge) got
  HTTP 402 "Your prepayment credits are depleted" on all 6 calls; no images made. The key's project bills **prepaid
  credits**, not a free tier as GEN first reported; about 70 images were made across the rounds. To go on: top up the
  credits in AI Studio (project → billing), then `tools/gen_sheets.py` runs `k2-homes` and `c2-fix` as they are. Until
  then the homes are missing and the loop's split stays the stand-in.
- GEN's round 9 picks (dispatcher's booth #2, gate with barrier #2, mine #2, Prospector #1, classes #1, growth marks
  #1) are cut and on `main` (c149e6b).
- **Decided overnight for I1 (to confirm):** Office keeps the person-placed cards (drag, fold, stretch unchanged);
  Camp lays the same buildings on the v3 rows and loop, **taking its rows and order from the Office positions** (by y
  into rows, by x within a row; the work's order only for buildings never placed); the lookout and the catapult stay
  pinned to the walls. Nothing is dragged in Camp itself.
- **21:06 check-in.** The owner topped up the Gemini credits; GEN's fourth run made 7 images. GEN stopped on a question
  for the owner; the PM session answered it (homes #1, track pieces #2, as GEN recommended). V3: the stations, the
  Prospector, the classes and the growth marks are in the preview (2a81827, aa4dff7). **I1 steps 1 and 2 are on `main`**:
  the real Camp drawn in v3 (807c4fe) and the steward, bubble, scroll and quick actions (a6f1a72); step 3 under way.
- **21:15.** The person's home (k2 #1, merged by the PM session from GEN's branch, 689113c) stands east of the Review
  gate in the preview, a toggle cycles the seven kins (bd4aa2b). The track junction is still the stand-in: GEN's c2-fix
  draws the branch 1.5× wider than the straight and over 4×3 tiles; a junction on one 64-px tile is still wanted.
  I1 steps 3 and 4 merged: the ork's console and the task's history (3546145), the score on the flying cart and in the
  HUD (d085528). Decided: the flying cart shows only what is recorded (tokens, $ on an API key); the per-cart share of
  the limit's window goes to Later (a recorder reading the limit before and after a run).
- **21:20.** I1's five steps are all on `main` (growth marks: abce1c0); I1 now polishes (the window line dropped,
  carts turning on the columns, name chips, a steward console for buildings without orks, Office's overlap, Camp's
  Build… into a row's free slot). **I2 started**: the Task board's inside (the dispatcher's booth), with stand-in art.
  **For you in the morning:** GEN has the inside's art ready to generate (booth interior, cards, panels) but waits for
  your yes before spending credits: `python tools/gen_sheets.py u6-inside u6-cards u2-panels -n 3 --max-calls 9`.
- **21:35.** **I2 merged** (5ab8a4b): the Task board's inside, entered by the second click — three boards with the
  cards as parchment (ork tasks) and stone (your to-dos), flags as checkboxes, drag between boards, the Taskmaster and
  orks walking inside; Info on a merchant's panel on the right; Exit and Esc; stand-in art until GEN's run. I2's own
  call, to confirm: Office and the phone keep today's large card. Demo traffic added by I1 (56d2db5): carts move, the
  siding holds the backlog, the score shows two demo weeks. Started: **M1** (Mission 1 on the stations, the catapult
  finale, its rewards recorded) and **INV** (growth by missions and the score, the class portrait, the home at the
  gate, the inventory with placed items).
- **21:45.** I1's polish all on `main`: carts face along their travel (c1 has side views only — a front view is an art
  gap), name chips clear of doors and stewards, a steward console for buildings without orks, Office's pool card fixed,
  Camp's Build… into a row. INV step 1 on `main` (ae0b77e): portrait stages by missions, lean weeks and levels; teal eyes
  at stage 4. Next for I1: the phone on Camp v3, then stabilisation (the full suite and browser tests green).
- **22:15.** **INV done** (cba3d44): an item whose cell a new building or a moved row takes goes back to the inventory
  quietly; the one line about it waits in the Items panel only. **I1's phone on `main`** (8338919): Camp v3 on the phone
  with the desktop's layout and sprites, touch pan and pinch by whole steps. **M1 done** (2714b7d): the drill on the
  dispatcher's siding, "Lift the barrier" as quest 3's press, the finale (the passed drill rolls off the weighbridge —
  the Publisher launches it if there is one, else it leaves at the buffer stop; "nothing left the town"), six quest
  deeds, `mission_done` opening stage 2 and the first-cart item. Fixes on the way: the quest-3 race (the flaky browser
  test), the cart on any Review gate's weighbridge drawn under the gate, toasts over the quest log's press, the portrait
  menu now scrolls (`test_the_sun_holds…` green). Screens: `img/m1/`. Open, sent to I1: the quest log panel covers the
  camp's bottom line; M1 centres the view at 40% as a stopgap.
- **22:18.** **M1 wrote Mission 1b** as a design only (first-mission.md §10, 63a1138); nothing is built until the owner has
  played Mission 1.
  - The check lives on the Agent pool (its `test_cmd` and rework loop), drawn as a proving siding with a semaphore
    arm that shows the verdict by position, never by colour.
  - The waybill gets one row per round.
  - Three quests: set the check (free); a scripted drill (no model); one real card checked within a $1 budget.
  - Rewards: a deed per quest and the item "proving stone". No stage is locked behind 1b.
  - Offered after a gated result later fails its tests; fallback three days after Mission 1.
  - About 5 days of work, and it starts by moving the quests into data files.
  - My calls on M1's open points, to confirm:
    - a project without tests gets a linter as its check, said plainly;
    - a slow suite gets a narrower command proposed;
    - a flaky test or a red `main` never counts as the trigger.
- **22:49.** Check-in.
  - I1 is still stabilising. It found the root causes of the red tests on `main` (e20ad1e) and is doing two more
    full-suite runs before it merges the fixes.
  - Everyone else is idle by design: INV and M1 are done, I2 waits for art, GEN waits for the owner's yes, V3 is done.
  - Nothing new is handed out: building 1b waits until the owner has played Mission 1.
- **23:36.** Check-in. I1 keeps stabilising and is not blocked. On `main` since the last check-in:
  - 06bd05c: a bench feed that dropped its last decision;
  - f6904e0: tests that raced their worker threads;
  - c9f90bf: three tests that read too early or at the wrong hour.

  The full run is not green yet; I1 is capturing the remaining tracebacks. The quest-log overlap is next after that.
- **23:42.** **I1's stabilisation (S9) is done.** The full suite plus the browser tests passed 4 full runs in a row
  (2149 passed), with nothing skipped or quarantined.
  - Product fixes among the root causes:
    - the phone's outbox could send a command twice;
    - `openBuilding` raced the building type's module loading;
    - the bench feed dropped its last decision;
    - the portrait menu overflowed the screen.
  - The rest were tests that read too early or mixed clocks.
  - `test_bench_sets.py` needs pytest in the `python` on PATH. That is the environment, not a bug.
  - One failure in `test_clan_fire_closed_command_and_full` is not reproduced yet; I1 will root-cause it if it
    returns.
  - Phone screenshots are in `img/i1/phone-390-*`, `phone-430-*`.
  - Last item for I1 tonight: the quest log covering the camp's bottom line.
- **00:22.** Check-in. I1 has the quest-log fix done locally and is not blocked. Before it merges, it is reading
  intermittent load errors in the drag and Workchief tests.
- **01:08.** I1's last items are on `main`:
  - c59aff8: the quest log is the camp's bottom inset, which retires M1's 40% stopgap;
  - 3467317: browser tests that left an orkspace behind, the root of the loot-cart flake and probably the clan one.

  The full suite passed twice at `-n auto` (2150). All sessions are idle; the morning summary is at the top of this
  section, and the check-ins have stopped.

## 15. Loops on the line; the launch date moved (15 October, with the owner)

**The line.** The line shows the flow; an agent's own loop is drawn inside the session (its bubble, the building's
inside). Between buildings:

- **Every cart runs one way round.** A return (a send-back, the brief to the Calendar) goes on, back along a **return
  line** under the lowest row, and in again: it never backs along a line, so carts never meet head-on.
- **Small switch stands** at every fork throw as a cart comes, so a return reads as "round again".
- **Carts keep their distance and wait in a pocket** beside their building's stop, never on the main line.
- **Services** (the Wiki) stand in a **back row along the palisade** with no track; an ork walks to them by a path.

The person's Office places win over neighbours (the owner: "it is their right"). What is guaranteed is the track:
fixed topology, full-width lines, no crossings, whatever is moved.

**A round's price, and placement as tidiness.** A cart going round again wears its round's cost (`round 2 · 🪵 18k`): the
second round reads as the price of rework. Placement makes trips shorter on screen only (work arrives at once), so it
is tidiness, never throughput: no layout measure, nothing in the score; the optimising game stays the score. The
Workchief's hint about a long trip moves to Later.

Full rules: [design-system-v3.md](design-system-v3.md) §4c. Priority: one way round, switches, pockets and a round's
price are P0, built now by the LOOP session; the back row and neighbours are P1.

**The launch date moved.** 19 October is off and there is no new date: the launch is the owner's "ready" (§13.1–2).
The devlog, Discord, the posts and the testers all wait for it together, since an empty room reads as a dead project.
The materials in `docs/marketing/` stay drafts.

## 16. The Agent pool becomes the depot (15 October, the owner)

The Agent pool is drawn as a **depot**: an engine shed standing on the line itself, the track through it west to
east, carts rolling in and out (the owner, to the art session); a bay per ork along its front (`max_orcs`, three by
default), so busy and free bays read from across the camp; the proving siding of Mission 1b is its exit track. Its
name and words stay. Carts for other buildings roll through without stopping. P0, built by LOOP next,
art `st-depot` by the art session. Full rules: [design-system-v3.md](design-system-v3.md) §4d.

**Ground (the owner, same day).** All track stands on a bed of path earth, never grass; building paths narrower (24
art px from 32); grass and earth drawn from several tiles by a fixed hash, all inner corners added. P0 after the
depot; art `g5-ground`. Rules: [design-system-v3.md](design-system-v3.md) §4e.

**Later the same day (the owner):**
- **The back row is taken out.** It was built (LOOP step 4) and showed long paths louder than the track for one
  building. The Wiki stands beside its busiest reader with no stop and one short footpath; other readers show 📖.
  The track bed (§4e) is what sets the track apart from the grass. Rules: design-system-v3.md §4c rule 1.
- **The Warchief is renamed the Workchief** in everything a person reads (the town hall's ork, its line, its chat,
  the docs, the README, the marketing drafts). Code keeps its names (`warchief`, `orc.town_hall`, files, event ids);
  the old word stays in the glossary's `was`. It also takes the word "war" out of the product's main character
  (Q18's care).
- **The logo is the Mechanic's head** from the role sprites, as drawn (to the chin, cleaned of stray pixels); the
  wordmark's font is **New Rocker** (the owner, in the art session; 96a17a3, 4cf46af). `tools/logo.py` builds the
  SVG, favicons, README logo and PWA icons from it. The landing draft keeps its own copy of the old font for now.
- **The depot's bays are openings, not tracks** (780747a): the line runs under the depot; a cart shows in a free bay's
  opening and leaves by the east gateway, so parallel work blocks no one.
- **Gemini's monthly spending cap is reached** (HTTP 429, 15 October). `g5-ground` (the varied grass and earth, the
  track bed's curves) waits until the owner raises the cap in AI Studio; the camp uses today's tiles meanwhile.

## 17. Towards the v4 targets (15 October, the owner)

The owner brought two target frames (`img/references/v4/target-camp.jpg`, `target-ui.jpg`). What is missing, in
order, and decided:

1. **The interface: design system v4** (P0, its own session). Camp's UI in the target's manner: thick wooden frames
   with a teal inner border, parchment panels, square bevelled icon buttons, a column of icon tabs at a panel's side,
   counters in frames, tab headers on teal plates. **A pixel font for headings, numbers and buttons only**; settings,
   waybills, consoles and any long text keep the readable text face (the owner: yes). The wordmark stays New Rocker.
   Office is not changed. Words follow CLAUDE.md (the target's "ORC LIST" is only a picture).
2. **The track:** a narrow bed just wider than the sleepers, steel-grey rails (design-system-v3 §4e rule 1).
3. **Grass and edges:** g5's grass is in (c6b753a); the camp's edges get wilderness (trees, bushes, a pond with a
   jetty), sparse inside the palisade.
4. **Scale and density:** orks about ×1.3 against buildings; rows tighter, the loop's empty middle filled; the Review
   board's campfire and the Home's pale ruin redrawn as houses in the common palette (teal, rust, grey stone).
5. **The palisade sharpened**, thinner and lower (the owner: as the PM advised; design-system-v3 §4.6 amended).

Sessions: **V4** (the UI), **LOOP** (track bed, scale, density), the **art session** (steel track, palisade, houses,
wilderness, the UI kit's textures if V4 asks).
6. **Density target (the owner):** at the default view a MacBook's screen holds **three rows of six buildings**,
   with their lines and the return line. This replaces §13.3's "at most ten buildings on the screen" and v3's rows of
   five: a row holds up to six (the depot counts as two). **Then "maybe even eight" (the owner):** rows hold up to
   eight; 3 × 6 must fit the default view, 3 × 8 at least the overview, and LOOP reports whether 3 × 8 fits the default
   with carts' chips and orks' bubbles still legible. LOOP measures it at 1512 × 982 (a 14-inch MacBook's default)
   and 1470 × 956 (a 13-inch Air), and tightens gaps, path lengths and the lines' spacing before it shrinks anything;
   if a smaller default step is still needed, it says by how much.
7. **Orks smaller again (the owner, after seeing ×1.5):** about 1.5× smaller, by the target's ratio: an ork about a
   quarter to a third of an ordinary building's height, kept when the buildings shrink for 3 × 6.
8. **No palisade down the side (the owner: "it looks very strange").** The palisade runs along the back only; the
   sides are trees and bushes (the wilderness), the catapult against a short end of wall. design-system-v3 §4.6.

## 18. Reachable from the phone all day (15 October, the owner, from work)

The owner may be silent for three hours and then drop a task from the phone. Keeping the Mac awake only while carts
work (W3, `gui/awake.py`) lets it sleep in between, and then the phone cannot reach the town. **Decided:** a third
setting for `keep_awake`, **"Stay reachable from your phone"**: the machine is held awake whenever Orkline runs, a
phone is paired and the computer is on power — carts or not. The display still sleeps; on battery it falls back to
"while carts work" and the phone says so ("Your Mac is on battery and may sleep"). Offered once when a phone is paired;
plain words in Town settings. A laptop with its lid closed still sleeps unless a display is attached (macOS's rule):
said in the setting's hint. P0, small (about half a day).

**The heralds (the owner, same day).** External listeners and the Calendar stand on the back wall, above the rows;
their notices open upwards over the wilderness with full details, never covering a building. A notice that asks
something of the person stays until dismissed; the rest fold into a count after about a minute (the PM's call, to
keep the town calm). The catapult stays at the line's end. P1. Rules: design-system-v3 §4f.

## 19. The phone app's slow first load (15 October; planned, not started)

The owner: images take very long to load the first time. Causes, read from the code: 283 separate sprite PNGs
(1.7 MB); the phone listener answers every request with `Connection: close`, so each image is a new TLS handshake over
Tailscale (100–300 ms each through a relay); and the service worker is network-first for everything, so sprites are
fetched again on every open. **Plan (P0, about half a day):** keep-alive on the listener; sprites cache-first under
versioned URLs (network-first stays for the shell and data); the v3 sprites packed into a few atlases; everything
precached once when a phone pairs at home. A native app would not fix this by itself. **Not started: the owner asked
that nothing more is launched until he says so** (the account's weekly limit is near).

**The Wiki on the grass (the owner, same day).** The Wiki leaves the rows: it stands on free grass inside the loop,
among its readers (the depot, the Calendar, the Review board), with short footpaths to up to three of them; it fills
the loop's empty middle. design-system-v3 §4c rule 1 amended. P1, after §19 and the phone; not started (the owner
asked that nothing is launched until he says so).

## 20. The camp lays out its buildings itself; the person places decor and items (15 October, the owner)

Replaces "the person's places win" (design-system-v3 §4c rule 3, §4b.3 "a building placed in Office takes its row
from its Office position"). **In Camp nobody places buildings: the product lays them out in good order.** The person
places only decor and earned items (v3-prompts §14), which is where a camp becomes theirs. Office keeps its cards
where the person put them: that is the work look's own drawing and does not move Camp.

**The order (to be specified in design-system-v3 §4g when built):**
1. **By zones along the flow:** the way in (the lookout, and the inputs beside it: Drop file here, Router; the
   Calendar on the wall, §4f) → the work (the Task board's booth at line 1's start, the depot, Research's mine, the
   benches) → the checks (Review board, Inspector, the Review gate near the end) → the way out (the Publisher's
   catapult at the buffer stop).
2. **Pairs stand together:** return pairs as neighbours (§4c rule 2); services on the grass among their readers (the
   Wiki, §4c rule 1).
3. **Stable:** a new building takes the free place in its zone and the others move as little as possible, so the
   person's map of the camp holds from day to day.
4. Stations, heralds and the 3 × 6 density rules stay as they are.

P1 with the Wiki on the grass (one pass over `layout.js`); not started (nothing is launched until the owner says so).

**Plots: the empty places invite (the owner, same day; PM's rules).** With the camp laying itself out, the place a
building *could* stand is drawn as a **plot**: a lot staked out with rope, and a blank wooden sign or a blueprint on
a post. A tap (hover on the desktop) shows the building's **silhouette** standing there (its v3 sprite in shadow,
drawn by code) and one plain line: what it would do for this camp, why now, and its cost ("A Test bench: checks the
Grunts' work before it reaches your gate. Free to build; its runs cost as the pool's"). **Build…** opens the usual
build flow; **Not now** turns the plot back to grass for 14 days.
- **Few and earned by the camp's story:** at most two plots at once, chosen by what would help next (the campaign's
  next mission, a pain the town shows: failed tests → the Test bench, many meetings → the Calendar), never a
  catalogue.
- **Calm (decisions §1 rule 3, v3-prompts §14 rule 4):** no badge, no count, no animation calling for attention, no
  yellow; Office draws none. Nothing is locked behind a plot: everything stays buildable from Build at any time.
- The Workchief may name a plot once in its line when it appears.
P1, with §20's layout; not started.

**The main line and the person's quarter (the owner, same day; amends §20).** So as not to take the camp's making
away from the person:
- **Row 1 is the main line, laid out by the product:** the flow every camp shares, in order: the Task board's booth,
  the depot, the work stations (Research's mine, the benches), the checks (Review board, Inspector), the Review gate
  before the end; the heralds on the wall above it (§4f). Always in good order, the same in every camp.
- **Rows 2 and on are the person's quarter:** the person arranges them as they like, **in Camp, by dragging** a
  building onto another place in these rows (it snaps to the place; the track, the lines and the loop stay the
  product's, §4c rule 4). A new building that is not on the main line lands in the first free place there, and stays
  where the person puts it. The Wiki's place on the grass and the plots follow the same split: plots for main-line
  buildings appear in row 1, the others in the quarter, where the person may move them.
- Return pairs across the two parts are not forced together; the round trip shows as it is (§4c rule 9).
- Decor and items stay the person's everywhere on the grass.

**Three bands, made precise (the owner, same day; supersedes the two bullets above where they differ):**
1. **The wall band, laid out by the product:** along the palisade, the buildings that speak to the person — the
   lookout (External listeners), the Calendar, other buildings that bring notices, and Metrics (the camp's figures)
   if it is built. Their notices open upwards (§4f). No line of its own; their stops reach line 1 by short spurs.
2. **Line 1 and its row, laid out by the product: the processing.** The core work every camp shares — the Task
   board's booth, the depot (Agent pool), the Review board, the stations, the Review gate before the end.
3. **Line 2 and its row: the person's quarter.** Empty at first except for plots (at most two); the person builds
   and arranges it themselves by dragging, the track staying the product's. Further rows join the quarter.
The Wiki stands on the grass among its readers (§4c rule 1) wherever they are.

**Plots come after Mission 1 (the owner, same day).** During Mission 1 there are no plots: the quarter is plain
grass, and the mission's quests raise the core buildings themselves. Plots appear only once Mission 1 is done (the
person knows how building works and what each core building does), when exploring new buildings becomes the
interest. Until then nothing hints at buildings to come.

## 21. From the tutorial to the person's own camp: the charter (15 October, design)

The owner's question: how does the person move from Mission 1's drills to a camp built for their own goal? The PM's
proposal, written in [first-mission.md](first-mission.md) §11: **the charter**, at the start of quest 4 (the first
real work): "What are we building here?" — *my project* (a goal line; the Workchief proposes the first three to five
cards from the repository, the person keeps or drops each), *a routine to automate* (one of four, which brings
Mission 2 forward), or *just looking* (a sandbox). The goal hangs as a banner on the wall band; milestones, not
points; later missions and the quarter's plots are offered by what the goal's real work shows. P0 for activation,
after the owner plays Mission 1. Not started.

## 22. The timeline to the testers and Halloween (15 October, the owner and the PM)

The account's weekly usage limit resets **Wednesday 21 October, 11:00 UTC**; until then code sessions run only when
the owner says so, and as few at once as possible.

| when | who | what | gate |
|---|---|---|---|
| Thu 15 – Sun 18 | owner | plays **Mission 1** on the desktop to the end, notes what breaks or bores; uses the phone over Tailscale; sends the **written IP confirmation** request (the project is personal, predates the job) | — |
| Thu 15 – Sun 18 | PM (docs only) | the testers' package refreshed (guide, invite, questions), the **E1 clean-install checklist**, the Halloween devlog draft | — |
| Mon 19 – Tue 20 | one dev session | fixes from the owner's Mission 1 notes (blockers only); **the phone's first load** (§19) | owner says "go" |
| Wed 21 – Thu 22 | one or two dev sessions | **the charter**, "My project" path only (§21; the routine path later); **E1**: a fresh macOS user, install → end of Mission 1, every break fixed | — |
| Thu 22 | dev | **release 0.3.0 "Orkline"**: `__version__`, `updates.json`, plain notes | — |
| **Fri 23** | owner + PM | **go / no-go for testers:** the owner finished Mission 1 alone; E1 passes; 0.3.0 out; no P0 open | go → testers |
| Sat 24 – Fri 30 | 3–5 testers | developers from the owner's own circle, personal machines, their own projects; Mission 1 and a week of use | — |
| Fri 30 | owner + PM | **go / no-go for marketing:** at least 3 testers finished Mission 1, no blocker | go → launch |
| **Sat 31 (Halloween)** | owner | **marketing starts:** the devlog's first post, Discord opened, the places' posts by hand (docs/marketing/); a Halloween touch in the camp (seasonal decor items, one small art sheet) as the hook | — |
| 1 – 14 November | all | feedback gathered, fixes; measured: Mission 1 finished, back within 7 days | — |
| from ~16 November | owner | **inside the company**, only after the written IP confirmation: a 20-minute demo, then volunteers on personal machines | written confirmation |

**Cut until after Halloween (P1/Later):** the three bands' auto-layout and the person's quarter, plots, the Wiki on
the grass, Mission 1b, the phone's v4 screen and landscape view, the charter's routine path. The look stays as it is
on `main`. launch-prep.md §4's measures move to about 1 December.

**The wall band holds the border and the dispatcher (the owner, same day; amends the three bands above).**
- **The wall band, left to right:** the lookout (the way in) · Drop file here · the **Task board** (the dispatcher's
  booth with its siding, between the wall and row 1) · the Calendar and any other notice-giving building · Metrics ·
  the **Publisher's catapult at the right end** (the way out, throwing over the back wall). Everything that crosses
  the camp's border, in or out, stands on the wall; the dispatcher stands among them.
- **The Task board dispatches to every row:** its siding joins line 1 at its start; a cart for a building in any row
  goes from the siding along the loop (line 1, the right column down to line 2, the return line) to its stop, so the
  board visibly feeds the processing row and the person's quarter alike.
- **The catapult's track** is a spur up from line 1's east end to a buffer stop by the wall; the Review gate stands
  at the east end of row 1, so a passed cart rolls a short way to the catapult. The buffer stop on line 2 is retired.
- **Row 1 (processing):** Router · Transformer · the depot · Research · Script · the benches · Review board ·
  Inspector · the Review gate (with the person's home beside it).

**No Town Hall in the camp; its door is the person's home (the owner, same day).** Camp no longer draws the Town Hall
as a building. The Workchief stays (the command bar's "Ask the Workchief…", the portrait, the line at the camp's
foot); the hall's panel (its roles, their spend, its settings) opens from **the home's menu**, which becomes the
person's one place: *Since your last look* · *You: profile and deeds* · **Items** (the inventory, moved here from
its button under the portrait) · **The Workchief's council** (the Town Hall's panel) · *The charter* (once set) ·
*Town settings*. Code keeps the `town_hall` type and its orks (CLAUDE.md: identifiers stay); Office keeps its card,
since the words do not change between looks. Spec 13.

**The camp's lines, final shape (the owner, same day; supersedes the bands above where they differ).**

```
 wall │ lookout · Drop file here · Calendar · Metrics …………………… catapult ▸ (over the wall)
 0.5  │ [Task board]═siding        (Wiki on the grass)         [Review gate]+home
      │   ║ ◂══════════════ line 0.5: sent back, to the board ═══════════ ║
      │   ▼ left column down                                 right column up ▲
 1    │ ══▶═ depot · Review board · Transformer (the tutorial's buildings) ══▶═
 2+   │ ══▶═ the person's quarter (each line laid by a click on its semaphore) ══▶═
```

1. **Line 0, the wall:** the lookout (in), Drop file here, the Calendar, Metrics, and the catapult at the right (out).
2. **Line 0.5, the person's two touchpoints:** the **Task board** at the left (work goes in) and the **Review gate
   with the home** at the right (the person judges); the **Wiki** on the grass between them, its footpaths down to
   its readers on line 1.
3. **Line 1, the processing the missions build:** the depot (Agent pool), the Review board (the debates), the
   Transformer when the missions bring it.
4. **Lines 2 and on, the person's quarter:** a new line is laid by a click on the semaphore at the left column's
   junction ("Lay a new line"), not by a building; the Router keeps its own job (routing rules).
5. **One way round, clockwise from the board:** down the left column, east along the processing lines, up the right
   column to the Review gate; passed → the catapult; **sent back → west along line 0.5 to the Task board**, which is
   the return line (**confirmed by the owner**): every track stays one-way and a rework visibly goes back to the
   dispatcher; there is no return line at the bottom.
6. **The lookout and Metrics stand side by side on the wall, joined by a road** (the owner: "the first", not
   merged): what comes in from outside also becomes figures (issues opened and closed, mail, webhooks a week). Two
   buildings, one expertise each.
7. **Many readers, many Wikis (the PM, on the owner's question):**
   - **One Wiki, many readers** (line 1, the quarter): footpaths only to its **three heaviest readers** (reads in
     the last 7 days), crossing a line on a level crossing; the others get no path, so the grass never fills with
     paths. **Hovering (or tapping) the Wiki lights all its readers** for as long as the pointer stays: the whole
     relation on demand, nothing permanent. Later: 📖 in a reader's bubble while it reads.
   - **Several Wikis** (the project's docs from the charter, a game design's, personal notes): each its own
     building. The first stands on line 0.5's grass as the camp's library; every other one stands on free grass at
     the point closest to **its own** readers (the same rule), wherever they are; two that want the same spot take
     the next nearest. Each draws paths to its own three heaviest readers.
   - **Wikis are on the grass, so the person may move them** like decor (drag, snapping to free grass, never on
     track, bed, paths or against a building); a moved Wiki keeps its paths, redrawn to its readers.

## 23. A process as a line: BMAD (15 October, the owner and the PM)

A staged process (BMAD first) is one line of the quarter; its stages are one-bay Agent pools along it (one role, one ork each: no new building type), the
depot once where work runs in parallel; a story split turns one cart into several; **debates after a stage are the
station's council annex** (on per station or for the whole line, its price said first; default after the PRD and
the architecture), not extra buildings; the person's approvals are barriers on the line. Priority medium (P1),
after the testers' first feedback, delivered as a line template. [process-lines.md](process-lines.md).

## 24. Negative feedback in a camp of cheerful orks (15 October, the owner's question; design)

The risk: the person likes the orks and does not want to upset them, so they pass weak work and skip 👎, and the
town cannot learn (the quality guard of the score and Mission 5b live on it). **The answer: feedback is never a blow
to an ork; it is an order on the work, and it visibly makes the camp stronger.**

1. **Critique goes to the work, never to the ork.** The words at the Review gate are about the result: *Needs
   another round* (with a note) and *Not this* (with a reason chip: did the wrong thing · broke something · too
   much · unclear), never "reject" or "bad ork". 👎 stays in the data; the button says what it does.
2. **Orks are never sad.** No sad face, no slump, no "fired". A cart sent back makes its ork **roll up its sleeves**
   (one frame, the cart back on the line as *round 2*); the Workchief's line keeps the camp's humour: "Back to the
   anvil, lads, the boss wants it sharper."
3. **The orks ask for it.** At the gate the waiting ork's line invites the note: "Be straight with us, boss: what
   would make it better?", and the reason chips make it one tap, the note optional.
4. **Feedback visibly pays.** A note that leads to a kept improvement (the outer loop, Mission 5b) hangs as a
   **lesson** in the building — a scroll pinned on its wall, its line readable on hover ("check the tests before
   the gate — from your note, 12 Oct") — and counts toward the building's **Renown** as a 👍 does. The Workchief
   says it once: "Your note taught the Grunts something." A deed for the first such lesson: *Hard but fair*.
5. **Said plainly where money is:** a cart sent back at the gate costs less than one that breaks after it; the
   waybill shows the round's price and what the note saved, so honesty reads as thrift, not cruelty.
6. **Calm by default still holds:** no nagging for feedback; a result passed without a word is fine.

Priority: wording and the sleeves frame are small (P1 with the next gate work); the lesson scroll comes with Mission
5b (the outer loop). Not started.

## 25. The settlement: joy from decisions, leisure on the grass, the home's room (15 October, the owner)

From the owner's note on the settlement and his answers: the orks are **glad after the person's decisions** (pass or
send back at the gate, a question answered, a building fixed) and **neutral otherwise, never sad, nothing decays**;
joy shows on the orks and on their icons at the bottom, no scale in the HUD; **the grass is the person's** for
relaxing pieces placed freely (bushes, benches, fountains, a bar, a carousel, the class's piece), and **idle orks
walk to them**; **work buildings have no levels** (the Renown footings and banners leave the map; quality by look
later); **the home becomes a room** with the person's growing figure and the deeds as trophies on its walls
(silhouettes for the rest, no "?"); coins and furniture are a second stage; **names stay**, the trains are the look.
The score stays the honest measure. [settlement.md](settlement.md). Not started; specs on the owner's word.


## 26. Who builds: agy or Claude, and the night run (15 October, the owner and the PM)

The first two agy branches, reviewed: spec 13 (small, one area) was about 85% done and needs one short round; spec
01 (caching, sockets) passed every test yet left old sprites stuck after an update and loosened the port's
protection unasked. Hence: **every spec says who builds it** (agy for small one-area specs; Claude for caching,
networking, security, data loss, and every pro or multi-module spec); **the owner starts agy and one Claude session
in the evening, on different files; the PM session reviews and merges in the morning.** Each spec names its files
("change nothing outside them") and asks for a behavioural browser test. The saving is in Claude's weekly limit: a
review costs about half of writing the code, so agy pays on small specs and barely on hard ones. The split and the
flow: [specs/README.md](../specs/README.md) "Who builds".

## 27. The concept is frozen: only changes to what exists, and simplifications (15 October, the owner)

The concept is checked on one person and grows faster than the product (92 design docs, no tester yet). So, from
today, **an idea is taken only if it changes or improves a mechanic that already exists. No new mechanics, buildings,
systems or concepts.** The one exception: **a simplification** of the product or of a feature (fewer steps, fewer
words, a thing removed or merged) is always welcome.

**How the PM session applies it.** Every idea, the owner's or an agent's, is sorted before anything is written:
- **improves an existing mechanic** (Mission 1, the Review gate, carts, the console, the phone, the camp's look,
  the onboarding, install) → taken, prioritised as usual;
- **simplifies** → taken, and ranks above an improvement of the same size;
- **new** (a new mechanic, building, resource, currency, system) → **No** for now; one line in
  [open-questions.md](open-questions.md) "After the testers", no design doc, no spec.

**What it means for work already designed:**
- Specs already written keep their order (specs/README.md): they rework existing mechanics (the camp's layout, the
  home, the depot, the phone).
- **The settlement (§25)** is new (leisure pieces, idle orks walking, the home's room, coins): no specs; it waits for
  the testers. **BMAD lines (§23)** and **Mission 1b** stay after the testers, as already planned.

**When it lifts:** after the testers' numbers, about 14 November (§22), and only if they hold:
1. of 3–5 testers, **at least 3 finish Mission 1**;
2. **at least 2 come back** within 7 days without being asked.
Below that, the work goes to what stopped them (install, Mission 1, the first five minutes), still under this rule.

## 28. Mission 1 as a scene (16 October, the owner)

From the owner's look at Mission 1: the onboarding is one fork after the class: *I'm new* → Mission 1, *Punk ork* → a ready town from the presets or
the planner; the empty town leaves the first session (spec 17a); the
window's chrome is put away and the stage zoomed, the Workchief walks in and speaks **on the map**, not in the line at
the foot; each building raised opens and is walked through in two or three steps (spec 17b, Claude). The first win
moves to about 4 minutes. An improvement of an existing mechanic, so inside §27. [first-mission.md](first-mission.md)
§12. P0 before the testers.

## 29. Darker, richer grass (16 October, the owner)

Camp's light grass draws the eye from the buildings and the signals. Of four previews
([img/grass-variants.png](img/grass-variants.png)) the owner chose **B**: saturation +30 %, brightness −25 %,
contrast −10 %, applied once to the grass tiles (the grass pixels only in the tiles shared with the path) and to the
Camp grass tokens. A colour change, not a re-cut (CLAUDE.md "Art"). Spec 18.

## 30. Camp's camera stays close; the wilderness is composed (16 October, the owner)

1. **No far zoom-out in Camp.** Pulled back, the buildings stop reading and the empty wilderness fills the screen.
   The default view (the railway across the whole screen) is the farthest; the wheel scrolls **down** the lines,
   since new lines are added at the bottom; closer zooms stay. Office keeps its map. Spec 19 (agy).
2. **Trees and bushes are placed, not scattered.** Today's hash on a grid reads as random. Hand-composed groves on
   named places round the camp (a pine band behind the wall, groves down the sides with gaps, the corners, the pond),
   the grass by the camp left open for the person's own pieces. Spec 20 (Claude); the owner signs off the shots.
Both improve existing mechanics (§27).

## 31. Entering a building; its things are its data; doors (16 October, the owner)

A click on a building in Camp dims the camp and shows the building **in the middle, roof off, on the whole screen**;
settings behind a gear, no permanent panel; Exit and Esc. In every room **the building's data are things** and the
person acts on them (the Task board's cards already are). Before the testers: the screen and the **Agent pool's** and
the **Review gate's** rooms (their art made by the owner, inside only); External listeners if time allows; the rest
after. **Doors:** an ork walks only into a building with a doorway; the 13 without one are open-air, their ork works
beside them; a building redrawn from now on gets a standard front door, its outside and inside made on one sheet.
[interiors.md](interiors.md), specs 21–24. An improvement of existing mechanics (§27).

## 32. The new art is cute orkish steampunk; doors anywhere, but marked (16 October, the owner)

Buildings will be regenerated (for their doors and their rooms), and **the new art adds steampunk** to the camp's
cute orkish cartoon: brass and copper pipes, boilers with steam, gauges, cogs, rivets, levers, bolted on crudely,
orkish first. A style frame first (interiors.md §6, card s1: the depot and the Review gate, outside with a doorway and
inside roof off, on one sheet), approved by the owner, then building by building. **Doors** need not be in one place,
but every doorway is marked at the cut (manifest `doorway`), so the ork walks to it wherever it is. A change of the
existing look (§27).

## 33. Steampunk before the testers; the room on black; big things (16 October, the owner)

1. **The steampunk art comes before the testers** (the owner: the art is generated, through agy, not drawn by an
   artist, so it is fast): style frame s1 first, then the depot and the Review gate outside and inside, then the
   other buildings Mission 1 shows. The testers' date stays (§22).
2. **A building is entered on a black screen**, not over the dimmed camp: nothing of the town distracts.
3. **Big things, not papers on a table:** a room is large, so its work is a few large props on the floor's lots
   (stone slabs and planks with carved titles, large crates with a bubble holding the title), each at least about a
   sixth of the room's width, at most six to eight shown; detail opens on a click. [interiors.md](interiors.md) §2.
4. **The style frame s1 is approved: candidate 1** (the owner, same day), kept as
   `docs/design/img/references/v3/s1-steampunk.png`; every new sheet follows it. Its rooms are too shallow for big
   props, so the final rooms (cards i-depot, i-gate) ask for a deep floor seen from above.
5. **A room is seen top-down, as an old JRPG's interior** (the owner, same day): the floor from above, the back wall
   a band with its face, the other walls thin rims. s1's side view sets the style only, not the view. Every room
   card asks for it ([interiors.md](interiors.md) §1, §6).

## 34. The daily rhythm: product here, art and easy code in agy, hard code in Claude (16 October, the owner)

The PM session prepares a **batch** twice a day (morning, as the owner leaves for work; night, as he goes to bed):
the agy tabs to open, files not overlapping. **Art** goes wholly to agy, 2–3 candidates each, the owner picks and
the PM session cuts. **Code** splits by difficulty: easy specs to agy, hard ones to Claude sessions the PM session
runs. Reviews and merges stay with the PM session. [specs/README.md](../specs/README.md) "The daily rhythm".

## 35. Five buildings; three tracks (16 October, the owner)

1. **The product's buildings for the first start are five:** the Task board (`fields`), the Agent pool
   (`barracks`), the Review gate (`loot_vault`), External listeners (`watchtower`) and the Wiki (`scrolls`). The other
   types are **hidden** from everything that offers a building (the Build dialog, the Workchief's planner, the ready
   towns of *Punk ork*); a town that already has one keeps it working. A simplification (§27). Spec 26. The Review
   board (`council`) is not among the five.
2. **The art goes to the five only:** `art-steampunk-all` is cut to `a-room-kit` and the five sheets; the other
   buildings' sheets wait (Later). agy's limits are not spent on what the first start does not show.
3. **Three tracks, in the owner's order of importance:**
   1. **the five buildings work**: the owner tests them on the product; the PM turns what he finds into short fix
      lists, building by building, for their work and their UX;
   2. **it reads as a game**: sprites, animations, the camp's look, on those five buildings, the orks and the carts;
   3. **the first day**: install, the onboarding, Mission 1.
   The first day's dated items run alongside, not after (the PM, agreed by the owner): E1 on Wed 21 October,
   release 0.3.0 on Thu 22 October, spec 17b (Mission 1 as a scene). The testers' date stays (§22).
4. **Mission 1 is four quests** (the owner agreed with the PM, same day): board → pool → gate → listen. Quest 3½
   (the Office look) and quest 5 (two cards at once) leave the first day; the Office look and parallel runs stay in
   the product. A simplification (§27). Spec 27, before 17b.

## 36. The scope is the three tracks; everything else is a hypothesis for later (16 October, the owner)

Until the testers' numbers (§27), work is only on **the three tracks of §35**: (1) the five buildings work,
(2) it reads as a game, (3) the first day. **Any idea outside them**, the owner's, the PM's or an agent's, and any
spec already written that serves none of them, goes to [open-questions.md](open-questions.md) "After the testers"
as **one line, a hypothesis**: no doc, no spec, no session, no art. It comes back only after the testers, if their
numbers or words ask for it.

Parked by this decision: the phone's new UX (spec 10), Halloween decor (spec 04, and its post), the camp laying
itself out and what hangs on it (specs 06, 07, 08, 09), the BMAD line (15), Mission 1b (11), the optional 12b, devlog
02. Kept, with their track: specs/README.md "The list". The phone that already works stays as it is; it gets fixes
only if it breaks.

## 37. After AgentCraft: five P0s on positioning and the first day (16 October, the owner)

A study of AgentCraft ([marketing/competitors/agentcraft.md](../marketing/competitors/agentcraft.md)): a closed,
free, one-person "RTS for agents"; 320k views at launch, ~200 npm installs a week and 309 in its Discord eight months
on. Interest in the image is proven, the habit is not. Its niche is attention (who waits, who idles); ours is the path
of a result to the person's decision. Taken as P0, all inside §35–§36:
1. **One line of difference** everywhere a tester looks (README's top, the onboarding's first screen, the invite,
   the guide): *a camp where work rides from the board through the orks to the Review gate, and nothing passes
   without you.* Never "RTS", never "command your agents like units".
2. **No orc/orchestration pun in headlines**, posts or first lines (the pun is taken by a talk on AgentCraft); the
   interface keeps its words (ork, orkestration). The public name is **Orkline** everywhere.
3. **The Review gate is the centre** (track 1): pass or send back at one glance, the waybill says what was done, what
   was touched, what it cost. The testers are asked how long a decision took and whether they came back for it.
4. **The first day is no longer than the competitor's**: one install line, the first cart at the Review gate as early
   as Mission 1 allows (Mission 1 in four quests, §35.4; anything not leading there leaves it).
5. **Trust said plainly** where the tester reads it first: local, no accounts, no API keys, nothing sent by itself;
   usage stats off until you say yes; the first real work read-only.

Not now (the owner): the "Grunt" name and the repository's name; the owner renames the organisation and the repository
himself. The licence is already Apache 2.0 (README), so the study's "decide the licence" is done: say it.

## 38. The orks stay; when we would look again (16 October, the owner)

The orks stay: they carry the product's meaning (rough, hard-working hands whose work the person checks at the Review
gate), the art, words, voice and Mission 1 are built on them, and a new image would be a new concept (§27). Orks are
a common fantasy image; the risk is copying one franchise, not orks. So we keep our own look and never take that
franchise's frame (minimap, portrait, ability grid), its green-and-red palette, its silhouettes or its words
(names of units, races, battle cries).

The risks and their answers: looking like a clone of AgentCraft (the one line of §37 leads, not the orks; the
"-craft" name goes with the owner's rename); orks feeling unserious at work (Office, the same town without sprites,
offered to the testers as a normal choice); words recognisable from that game, such as "Grunt" (left as they are for
now, the owner; looked at again after the rename or if testers notice).

**When we look again:** after the testers, only if **two or more** of them say on their own, unprompted, that it
looks like AgentCraft or like a copy of that game (the guide's questions "what is Orkline for" and "a game or a
tool" are where it shows). Otherwise the question is closed.

## 39. The Review gate checks by what the result is (16 October, the owner)

Two voices now (the interview of 16 October and the owner): **code** results are not read one by one, there are
too many; **what goes to people** (tasks, documents, replies, posts) is read by eye, each one, before it is sent. So
the Review gate asks for the person's look where it is worth it:
- **what leaves to people** (a reply, a post, a task or a document for someone else): stops at the gate, one by one,
  read before it goes. This is what "nothing passes without you" means;
- **code**: passes on its checks (tests, the Warder, the budget) and gathers at the gate as **one batch a day**; the
  person looks at the batch once (what changed, what it cost, what failed) and passes or sends back what needs it.
**The daily check** (the owner, same day): once a day, at an hour the person sets, one ork at the Review gate checks
everything code that reached the branch that day against its spec and tests and fixes what fails, on that branch, on
a budget said first; then the batch waits with its report (what changed, what it fixed, what it could not, what it
cost). Nothing is merged by it: the person passes the batch. No new building: it is the gate's own run (the hour is a
setting of the gate, not the Calendar).
An improvement of the existing gate (§27), track 1, **P1**: its spec is written after the owner has tested the five
buildings, so it carries what he finds. Mission 1 stays as it is (its drill is one cart, passed by hand). The tester
question on how they check agents' work counts towards it. "The plan passed before the work" stays a hypothesis.

