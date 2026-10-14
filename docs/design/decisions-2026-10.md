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

**The calendar (the owner, 2026-10-13):** until the end of the week of 12 October, the backlog's tasks; from 19 October,
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
