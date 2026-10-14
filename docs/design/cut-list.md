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
| **The phone's places** (the town's rules by where the phone is) | **Drop** (§3: the owner does not use Orkline's phone app) | far from the main scenario; Tailscale and the place rules are upkeep for a few | **P1** |
| **The phone app** | **The console on the phone** (§3a): the ork slots list, ❓ and 🔥, the console and the waits, built once for both; out of the README's first screen until the owner switches to it | the owner would move from Claude Code's phone app to Orkline's once it does more; what it needs is what the desktop already gets | **P1**, after the console; the README line **P0** |
| **The Test bench and the UX bench** | **Freeze**, through Improve only ([catalog-shelves.md](catalog-shelves.md)); gate in [improve-buildings.md](improve-buildings.md) §12.4 | the biggest area, made for the owner and contributors | — |
| **Wiki, Research, Audio briefing** | **Freeze**, More shelf | — | — |
| **Orkspaces beyond the first** (F2–F8, each in its biome) | **Hide** from the first session: one town until the person asks for a second | small in code; one more idea in the first fifteen minutes | **P1** |
| **The builder** (new buildings from words) | **Keep**, out of the first fifteen minutes | the wow, and a risk: a weak generated building is a tester's first bad impression | — |
| **Onboarding** (role, industry, mascot, a typical day as chips, intents, quiet hours, look) | **Cut to the AI tools found**; the rest to Settings or out (decided 2026-10-12) | the first session becomes a game's first mission ([first-mission.md](first-mission.md)) | **P0** |
| **Two looks, Camp and Office** | **Keep**, with a rule: Office is tokens and words only, never a layout of its own | Office answers "it is a toy"; a second layout would double every screen | — |
| **Growth** (deeds, the mascot's stages) | **Keep**, no new work; never in the way of the main scenario | small; it carries the camp's voice | — |

## 3. The owner's answers (2026-10-12)

1. **The phone:** corrected the same day. The owner uses **Claude Code's** phone app every day, **not Orkline's**. So:
   - Orkline's phone app is **frozen**: it works as it is, no new work on it;
   - its **places** are **dropped**: rules on top of an app nobody uses;
   - **the README's first screen stops selling it** ("the phone app shows them too"): what the author does not use, a
     first tester should not be promised;
   - later, by what testers ask: perhaps no app of Orkline's own at all, only 🔥 and ❓ sent where the person already
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

### 3a. The phone, a second time (2026-10-12)

The owner: "I will move from Claude Code once Orkline's phone app does more." The owner is the main user and
"useful to me" counts as success, so the phone is not frozen for good. But "does more" is a guess until it is said
**what work** the owner does on the phone.

- **No phone features of its own.** What the phone needs is what [ork-console.md](ork-console.md) gives the desktop:
  the ork slots list with 🔥 and ❓ (§8), the console to answer, stop and read a session with its spend (§7), the
  waits with their reason and Start now / Run anyway (§19). Built once, drawn for both.
- **P1, right after the console works on the desktop** (P0). Orkline's own phone app as it is today stays frozen until
  then; its places are still dropped.
- **The test is the owner's switch.** The README promises the phone again on the day the owner stops opening Claude
  Code's app for this town's work.
- **The owner's answer: what is done on the phone every day.** Ideas for the product are thrown in, talked through and
  sent to be built; sometimes a picture is made with Gemini. The gain of doing it in Orkline: one place, no switching
  between sessions, nor between Claude and Gemini. So the bar, and nothing past it:

  | on the phone | made of | priority |
  |---|---|---|
  | **1. Drop an idea** in one press, text or voice | the Task board's **Ideas** lane (notes; taken by moving into To Do, [night-round.md](night-round.md)) | P1, with the phone console |
  | **2. Talk an idea through** with an ork, and come back to the talk later | the console (§7 of [ork-console.md](ork-console.md)) on the Task board's steward; the card is rewritten from the talk | P1 |
  | **3. Send it to be built and follow it** | Send to ▸ the Agent pool; the ork slots list, ❓ and the waits; pass the result at the Review gate | P1 (the console's parts) |
  | **4. Make an asset** (a picture from words, by the Gemini side, agy), **see it at once, edit it quickly** | `realm/painter.py` already paints from words within a marked region; new: a picture for any card, its preview on the card, a quick edit (mark a region, say what changes, a new version), Accept writes the file into the repository | **P1**: the owner's switch waits on it (§3b) |

  Items 1–4 are the switch test: once they work on the phone, the owner stops opening Claude Code's app for this
  town's ideas, or says what is still missing.

### 3b. Assets, and reading on a small screen (2026-10-12)

The owner: making assets (pictures and the like) is an important step, with a preview and a quick edit; and with
Claude Code's app long answers are hard to read and questions get lost on a small screen.

- **Assets are P1, in the phone's bar.** Built on `realm/painter.py`: one image call (agy by default) in an empty
  folder, the person's words, a marked region. What is new: any card can hold a picture, shown on the card at once;
  **Edit** marks a region and says what changes, and makes a new version beside the old; **Accept** writes the chosen
  version where the card says, in the person's repository.
- **Who it is advertised to** ([improve-buildings.md](improve-buildings.md) §12.4, reworked 2026-10-12): new builders
  making games and apps with AI, for whom icons and illustrations are a plain gain, yes, once built; the classic game
  developer community, no.
- **The owner's game meets gate 1 of §12.4** for the Alchemist's side: two weeks on the owner's own second project.
- **Long answers and lost questions** are the console's problem on every screen, not only the phone's:
  [ork-console.md](ork-console.md) §20.
- **Talks lost across tabs** (the owner forgets where a thing was talked through): a talk belongs to its card, with
  one list of recent talks, [ork-console.md](ork-console.md) §21, P1 with the phone.
- **The phone in Camp, the laptop in Office** (the owner, 2026-10-13): the phone draws in Camp by default and carries
  the 💡 and gate actions beside items 1–4; missions stay on the laptop ([work-and-play.md](work-and-play.md) §4c).

### 3c. The phone with the computer off: a mailbox for decisions, not a town in the cloud (2026-10-13)

The owner: move the town to a simple backend (Firebase or the like), so it can be changed with the computer off; then
perhaps a native app instead of the PWA.

**Not a town in the cloud:**

1. **It breaks the README's first promise:** local-first, no keys, no accounts, no servers, the person's own login. A
   backend means accounts, holding other people's data (the town holds prompts, pieces of code, mail), security and
   privacy; a developer audience trusts it less.
2. **The work runs on the laptop anyway:** the orks run CLIs in the person's repository. With the laptop off the town
   cannot *do* anything; it can only *take the person's decisions*.
3. **Money and upkeep:** one person in alpha should not run a cloud holding users' data.

**What is needed instead: a mailbox for decisions (Later, after the phone works with the laptop on):**

- **The phone shows the town's last snapshot** and gathers the person's decisions: apply a 💡 item, answer a ❓, pass
  a result at the gate, drop an idea.
- **The laptop, waking, takes the decisions and applies them;** the truth stays on the laptop.
- **The relay sees only ciphertext:** a small relay, end-to-end encrypted with the key the phone already gets when it
  is paired, in the way of the usage stats' Cloudflare Worker (`tools/usage-worker/`): no town on it, only an encrypted
  queue of short commands and the last snapshot.

The promise holds, and the phone works with the computer off.

**A native app instead of the PWA: No, until a measured blocker.** A native app is store review, a yearly developer
fee, two platforms or a cross-platform framework, all kept up by one person; the PWA exists and web push works on iOS
since 16.4. Moved only if push is measured not to arrive, or putting it on the home screen is seen to stop people;
and then as a wrapper (Capacitor or the like) over the same web code, never a rewrite.
