# Design — the cut list: what to hide, freeze, merge or drop

Status: written 2026-10-12, the owner's ask ("what else can go, or be made much simpler"); nothing changed in code.
Builds on [catalog-shelves.md](catalog-shelves.md) (buildings), [simplify.md](simplify.md) (fewer minds, one word
each, 2026-10-07), [town-hall-roles.md](town-hall-roles.md), [ork-console.md](ork-console.md) §11 (priorities).

## 1. How to read it

The product is about 82,000 lines of Python. The biggest areas, by code (`orkcraft/` and the GUI's JS, grouped by
file name; rough): the Test bench and UX bench ~10,000; outside services (listeners, logins, Google, GitHub) ~5,200;
the phone (pairing, TLS, Tailscale, PWA, places) ~3,600; the night (Night round, Elders, improve, review, retros,
evolution) ~3,300; autonomy and the Council ~3,100; Wiki and Research ~3,000; onboarding ~2,200; the builder
~2,200; audio ~1,900; growth ~600.

Five verdicts, cheapest first. Code is deleted only when a part is both unused and in the way; everything else is
hidden or frozen, so older towns keep loading (CLAUDE.md, Wording).

| verdict | means |
|---|---|
| **Off by default** | stays, a person turns it on |
| **Hide** | not offered to a new person; one click away for whoever looks |
| **Freeze** | works as it is; no new work until its gate is met |
| **Merge** | two or more parts become one |
| **Drop** | removed |

## 2. The list

| part | verdict | why | priority |
|---|---|---|---|
| **The night's work in a new town** (the Mechanic's and Alchemist's improvements, $1 a night; the Mechanic's night check; the day's review; the Night round; the daily proposal at 06:20; the weekly self-audit **on opus**) | **Off by default** | today all of it is on (`realm/fastpath.py` `SETTINGS`): a tester wakes to money spent or a limit used that they never asked for. Offered after a few days of use, with its budget said plainly, by the Treasurer ([connections.md](connections.md) §3 has the shape) | **P0** |
| **The night's processes, six of them** | **Merge** into one flow, the Town Hall's night council ([town-hall-roles.md](town-hall-roles.md) §2): one switch, one budget, one morning brief. [simplify.md](simplify.md) §4 and §7 already go this way | **P1** |
| **Autonomy in three places** (the town's level, a building's own level and waits, a building's Freedom for its retro) | **Merge**: one Autonomy per ork ([ork-console.md](ork-console.md) §2), gates on buildings; the building's level, its own waits and its Freedom go | **P1** |
| **External listeners' sources** (Gmail, Slack, Jira, Confluence, Figma, Google, GitHub, schedules, webhooks) | **Hide** all but GitHub, a schedule, a webhook and a file | the main scenario needs GitHub; the rest are the owner's | **P0** (what is offered only) |
| **The phone's places** (the town's rules by where the phone is) | **Drop** (§3: the owner does not use Orkcraft's phone app) | far from the main scenario; Tailscale and the place rules are upkeep for a few | **P1** |
| **The phone app** | **Freeze**, and out of the README's first screen (§3) | nobody uses it yet, the owner included: the owner's phone is Claude Code's app. Not sold until a tester asks for it | **P0** (the README line) |
| **The Test bench and the UX bench** | **Freeze**, through Improve only ([catalog-shelves.md](catalog-shelves.md)); gate in [improve-buildings.md](improve-buildings.md) §12.4 | the biggest area, made for the owner and contributors | — |
| **Wiki, Research, Audio briefing** | **Freeze**, More shelf | — | — |
| **Orkspaces beyond the first** (F2–F8, each in its biome) | **Hide** from the first session: one town until the person asks for a second | small in code; one more idea in the first fifteen minutes | **P1** |
| **The builder** (new buildings from words) | **Keep**, out of the first fifteen minutes | the wow, and a risk: a weak generated building is a tester's first bad impression | — |
| **Onboarding** (role, industry, mascot, a typical day as chips, intents, quiet hours, look) | **Cut to the AI tools found**; the rest to Settings or out (decided 2026-10-12) | the first session becomes a game's first mission ([first-mission.md](first-mission.md)) | **P0** |
| **Two looks, Camp and Office** | **Keep**, with a rule: Office is tokens and words only, never a layout of its own | Office answers "it is a toy"; a second layout would double every screen | — |
| **Growth** (deeds, the mascot's stages) | **Keep**, no new work; never in the way of the main scenario | small; it carries the camp's voice | — |

## 3. The owner's answers (2026-10-12)

1. **The phone:** corrected the same day. The owner uses **Claude Code's** phone app every day, **not Orkcraft's**. So:
   - Orkcraft's phone app is **frozen**: it works as it is, no new work on it;
   - its **places** are **dropped**: rules on top of an app nobody uses;
   - **the README's first screen stops selling it** ("the phone app shows them too"): what the author does not use, a
     first tester should not be promised;
   - later, by what testers ask: perhaps no app of Orkcraft's own at all, only 🔥 and ❓ sent where the person already
     is (a push, Slack, mail), as the person already chose another tool's app for their phone.
2. **What is read from the night:** changes to the product (technical and product), and proposals to improve the
   person's ways of working. So the merged night council ([town-hall-roles.md](town-hall-roles.md) §2) makes exactly
   two things for the morning brief:
   - **changes:** what the orks changed in a building, or propose to change, with the numbers that say it is better
     (today's improvements of the Mechanic and the Alchemist, the night check, the probation of
     `realm/evolution.py`);
   - **proposals for the way of working:** what to do differently, new roads, work to drop (today's day review by the
     Mechanic and the Farseer, the daily proposal, the weekly retro).

   What makes neither is dropped with the merge: the Night round's marks on board cards unless they lead to one of
   the two. The Elders' answers to permission questions at night are not read but act (under Autonomy); they stay.
   The whole night stays **off by default** in a new town (§2).
3. **Orkspaces beyond the first:** not used now, thought to be wanted. They stay, **hidden from the first session**
   until a person asks for a second town; no new work on them until a tester does.
