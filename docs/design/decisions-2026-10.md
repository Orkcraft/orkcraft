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
| [town-readability.md](town-readability.md) | carts, orks and their link readable on a bright camp: outlines, reserved signal colours, badges only for exceptions, a spotlight on hover |
| [work-and-play.md](work-and-play.md) | Office at work, Camp as the game after work; one layout, two drawings (numbers ↔ things) |
| [dogfood-logs.md](dogfood-logs.md) | what is logged; what to switch on before the owner's game; what is missing |
| [improve-buildings.md](improve-buildings.md) §12.4 | the benches beyond Orkcraft: Later, with a gate; assets offered to new builders, not the classic game dev community |
| [distribution.md](distribution.md) | the doors where the audience installs: PyPI and a Claude Code plugin before the launch, a VS Code and Open VSX extension after the testers; a door, never a second face |
| [launch-prep.md](launch-prep.md) | the week's goal by 18 October; GitHub, the landing page and the materials prepared for the marketing from 19 October |
| [similar-products.md](similar-products.md) | the projects that show agents as characters in a game world (Pixel Agents and others): the category's ticket, not our difference; we run the work, they watch sessions |
| [open-questions.md](open-questions.md) | the owner's open questions (Q1–Q20) and the research to-do (R1–R10) |

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
a Claude Code plugin ([distribution.md](distribution.md)).

**P1, first:** the phone as the console (the commute home, [audience.md](audience.md) §2a); the town's clock and held work ([town-time.md](town-time.md)); a cart's id, its waybill and its origin
([cart-waybill.md](cart-waybill.md) §2a); assets on cards on the phone; Work gone type by type; the Town Hall's roles folded, then ork faces; the score
and the 💡 list; the yard as ground; each biome's palette.

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

