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
| **The phone's places** (the town's rules by where the phone is) | **Drop**, after the owner confirms it is unused (§3) | far from the main scenario; Tailscale and the place rules are upkeep for a few | **P1** |
| **The phone app beyond its core** | **Freeze**: it shows what burns and what asks, and lets the person answer; nothing more until testers ask | the README sells "the phone app shows them too"; that much stays | — |
| **The Test bench and the UX bench** | **Freeze**, through Improve only ([catalog-shelves.md](catalog-shelves.md)); gate in [improve-buildings.md](improve-buildings.md) §12.4 | the biggest area, made for the owner and contributors | — |
| **Wiki, Research, Audio briefing** | **Freeze**, More shelf | — | — |
| **Orkspaces beyond the first** (F2–F8, each in its biome) | **Hide** from the first session: one town until the person asks for a second | small in code; one more idea in the first fifteen minutes | **P1** |
| **The builder** (new buildings from words) | **Keep**, out of the first fifteen minutes | the wow, and a risk: a weak generated building is a tester's first bad impression | — |
| **Onboarding** (role, industry, mascot, a typical day as chips, intents, quiet hours, look) | **Measure first**, then cut to three screens and a minute | P0 is the measure: the time from first open to the town ([dogfood-logs.md](dogfood-logs.md) §3, the local event log) | P0 measure, P1 cut |
| **Two looks, Camp and Office** | **Keep**, with a rule: Office is tokens and words only, never a layout of its own | Office answers "it is a toy"; a second layout would double every screen | — |
| **Growth** (deeds, the mascot's stages) | **Keep**, no new work; never in the way of the main scenario | small; it carries the camp's voice | — |

## 3. Open questions for the owner

1. **The phone:** used daily? And its places (rules by where the phone is)? If places are unused, they are dropped.
2. **The night:** which of its outputs are actually read in the morning? Only those come back in the merged night
   council; the rest are dropped with it.
3. **Orkspaces:** used beyond the first? If not, F2–F8 are hidden, not only from the first session.
