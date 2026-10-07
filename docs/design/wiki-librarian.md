# Design — the Wiki's librarian: keeps, finds, places, checks

Status: written 2026-10-07; stages 1–4 (§11) built the same day, and with them the Calendar's own
line *from the Wiki: 2 to discuss* and the suggestions over the Warchief bar for `/note`. Where the
build went another way than this text first said, §12 says so. The pictures are on the design canvas *Scroll Dump
screens* (rows 4–6: the quality check, Quick note, the librarian and the meetings). It grows the
🗑️ Scroll Dump (**Wiki**) from "an ork that turns sources into pages" into the town's owner of
knowledge: a note goes in with one click, lands in the right place of the wiki, comes back out when
something needs it (a meeting first of all), and the wiki is checked for its quality on a schedule.

## 1. Today, and what is missing

What the Wiki does today (`core/workers/scrolls.py`, `realm/wiki.py`, [reference.md](../reference.md)):

- Its sources are read-only folders, git revisions or a Confluence space. The librarian ork takes
  them in (`ingest`) once they settle, writes linked pages, commits them, and a Clan Fire spot-checks
  a sample. Pages people own stay theirs.
- A task that reaches it (a cart, or a Barracks that reads it first: `notes`) is sent on as
  `knowledge.chunks` with the wiki's map and the three pages that share the most words with it
  (`lend`, `wiki.relevant`).
- `lint` checks contradictions, stale facts, orphans, broken links and the indexes, and writes `lint.md`.
- The Calendar (War Drum) asks for a meeting's document 2 h before it (`calendar.event_upcoming`,
  titled by the meeting, tagged `[meet:<id>]`, its ref `<calendar>:<id>`); a cart that comes back with
  the tag or under the ref becomes the meeting's document.

What is missing:

1. **No way to add a note.** The window has no button for it; a person writes a file into a source
   folder by hand. A cart into the Wiki is read as a task and sent on, never kept. The Pit keeps text
   in `.orkcraft/pit/`, which no wiki can read (`shelves.SKIP_DIRS`).
2. **Short notes get lost.** "Discuss the pricing tiers with Sergey tomorrow" names a person and a
   day, not a topic the wiki has a page for; the librarian files it somewhere, and nothing ties it
   to tomorrow's meeting.
3. **Finding is word overlap, Latin only.** `wiki.relevant` counts shared words of 4+ Latin letters
   (`_WORD = [A-Za-z]…`): a note or a meeting written in Russian matches nothing. A meeting's brief
   gets the pages that happen to share words with its title, not the notes left for it.
4. **Quality is checked only when someone asks.** `lint` runs from a button; its findings show
   nowhere in the GUI (the TUI's hut has a count).

## 2. Principles

1. **The files stay the truth.** A note is a Markdown file in a source folder; the meeting's agenda
   is a section of a wiki page. No database, nothing only the app can read. A person can edit or
   delete any of it in an editor.
2. **Rules first, a light model second, the agent last.** What rules can do (dates, names the wiki
   already knows, the calendar's events, links) is done without a model, at once. The light model
   (the Council's `fast_model`, as Task Fields titles cards) is asked only for what rules could not
   read, and never blocks Save. The librarian (the agent) writes pages at take-in, as today.
3. **Suggest, never decide alone.** Every guess — section, tags, links, the meeting — shows before
   Save and goes with one click. What was confirmed is not guessed again at take-in.
4. **One note, wherever it was written.** The Wiki's Quick note, `/note` to the Warchief and a note
   on the Task board are the same note and the same file.
5. **Handing over is by id, not by luck.** A note bound to a meeting reaches that meeting's brief
   because it carries the meeting's id, whatever words it uses.
6. **People's pages stay theirs** (as today): the librarian writes suggestions to `proposals.md`.

## 3. Wording

- The building's ork is the **Librarian** (today's word; it was *Wiki writer*, Camp *Scroll Scrapper*).
  The code calls it that already (`AUTHOR`, `"librarian"` jobs). In conversation it was called the
  keeper; **keeper** is already a word (`TERMS`: a building's steward, asked in plain words), so the
  interface never uses it for this ork.
- New entries in `realm/lexicon.py` `TERMS`: `quick_note` → **Quick note**; `to_discuss` →
  **To discuss** (an item a meeting should cover); `open_item` → **Open item** (an item waiting for
  a meeting with someone); `quality_check` → **Quality check** (the scheduled lint).
- Labels say plainly what happens: *Save note*, *Not for a meeting*, *Check now*, *Fix links and
  indexes*. The cost of a model call is said in money where it shows.

## 4. Quick note

### Where it starts

| Where | How |
|---|---|
| The Wiki's window | **+ Quick note** in the head, next to *Check the wiki*; opens the panel over the tree |
| The Wiki's card and Info | the quick action `wiki.note` (catalog), next to Ingest and Lint |
| The Warchief bar | `/note <text>` (a new word in `COMMANDS`, no model): the suggestions show over the bar; Enter saves, Tab picks another meeting, `@Wiki` picks the wiki when the town has several |
| The Task board | a note card gets **→ Wiki** (and the New note form a checkbox *Also to the Wiki*): the same file is written, the card keeps a link to it |

With several Wikis in the town, the note goes to the one the person names; else the one whose topic
is `team` or `general`; else the first.

### The panel

- The text (one line or many). Ctrl+Enter saves, Esc closes.
- **For the meeting** — a Calendar event the note is for, with *Not for a meeting*. With none
  picked and a person named, the line says the note stays an open item for that person (§6).
- **Section** — the wiki's sections (`WIKI.md`), one picked.
- **Tags** — chips, each dropped with ✕; *+ Add tag*.
- **Link to** — up to three pages, each with a checkbox.
- **Saves to** the file's path; **Take in now** (a checkbox, on by default); Cancel / **Save note**.

### How the suggestions are made

Each runs when the text stops changing for 400 ms; the panel shows what it has, as it comes.

| Suggestion | Rules (no model) | Light model, only when rules found nothing |
|---|---|---|
| **When** | `today`, `tomorrow`, a weekday, `14:30`, an ISO date (`daybook.parse_when`, grown: weekdays and Russian `сегодня` / `завтра` / `послезавтра`, weekday names) | — |
| **Who** | names the wiki already has: the titles and `aliases` of `pages/people/*`, matched in any inflection by stem (*Сергей*, *Сергеем*, *Sergey*) | the names in the text |
| **Meeting** | Calendar events from now to 14 days ahead; one that is on the day named and/or names a person named (its summary, its people) wins; ties go to the nearest | — |
| **Section** | `meetings` when a meeting or a person and a day are found; else the section of the best linked page | one of the wiki's sections |
| **Tags** | the `aliases` of the linked pages that occur in the text; the people named; `to discuss` for a meeting | up to 4 short tags |
| **Links** | `wiki.relevant`, fixed for any script (Unicode words, a stem of 5 letters), plus the people's pages | — |

The light model is asked once per note, with the text, the sections and the people's names, and
answers JSON (`{"who": [], "about": "", "section": "", "tags": []}`). Off in the sandbox, without
🪙, or when the Fast Path is off: the rules alone. A failed call loses nothing.

### The file

Saved in the Wiki's **inbox**, `config.inbox` (default `notes/inbox`, outside the wiki's own folder,
since a wiki is never its own source). The first note adds the inbox to `sources` by itself.

```markdown
---
kind: to-discuss            # note | to-discuss
section: meetings
meeting: 4f2a9c01d3e7       # the Calendar's meet id
meeting_title: Pricing review with Sergey
when: 2026-10-08 11:00
with: [Sergey]
tags: [sergey, pricing, to discuss]
links: [pages/people/sergey.md, pages/product/pricing-tiers.md]
from: quick note            # quick note | warchief | task board
written: 2026-10-07 15:42
---

Discuss the pricing tiers with Sergey at tomorrow's meeting
```

Named `<date>-<slug of the first words>.md`. Committed with the wiki when the next take-in commits.
Saving sends `wiki.noted` (a new event: the note's path) and, with *Take in now*, starts an ingest
of the inbox at once (the settle time is skipped for a note).

## 5. Placing: where the note ends up

Two parts, so that the agenda never waits on the agent:

1. **At once, by rules (the worker).** A note with `meeting:` puts a line under **To discuss** on
   the meeting's page, `pages/meetings/<date>-<slug>.md`, made when it is not there:

   ```markdown
   ---
   kind: meeting
   calendar: meet:4f2a9c01d3e7
   when: 2026-10-08 11:00
   with: [Sergey]
   owner: ork
   ---
   # Pricing review with Sergey

   ## To discuss
   <!-- to-discuss: kept by the Wiki from its notes; tick what was covered -->
   - [ ] The pricing tiers — [note](../../../notes/inbox/2026-10-07-pricing-sergey.md)

   ## Background

   ## After the meeting
   ```

   The block between the marker and the next heading is the worker's; a person ticks items there.
   A note with `with:` and no meeting adds an **Open item** to each person's page
   (`pages/people/<name>.md`, section *Open with <name>*).
2. **At take-in, by the librarian.** The ingest prompt gets the note's front matter as given, and
   the rules: keep the section, the links and the meeting as they are; make the tags `aliases`;
   write the meeting page's *Background* from the linked pages; add a line on each person's page.

The sections `meetings` and `people` are added to the `team` and `general` topics' `SECTIONS`
(with their page formats in `WIKI.md`); an existing wiki gets them at its next scaffold
(`wiki.scaffold` writes only what is missing).

## 6. Handing over: the meeting asks, the Wiki answers

- **The cart.** `calendar.event_upcoming` already reaches the Wiki when a road brings it, or when a
  Barracks that prepares the brief reads it first (`notes`). `lend` changes: it reads the `[meet:<id>]`
  tag (`daybook.meet_tag`); when a meeting page carries that id, the context starts with
  **Read first: the meeting's page**, then the pages it links, then the open items of its people,
  then `relevant` as today. The cart keeps the task's title and ref, so the brief still comes back
  to the Calendar by the return road.
- **The binding.** The worker matches the Calendar itself: the Wiki's `calendar` setting names a War
  Drum (default: the only one in the town). On `refresh` it reads that worker's events (as a Barracks
  calls `lend` on its notes): an open item for a person binds to the next meeting with that person
  (its summary or its people name them) and moves under its *To discuss*. Nothing is sent for this.
- **After the meeting.** When the meeting has ended (its end in the Calendar), the items not ticked
  go back to *Open with <name>* on each person's page, and *After the meeting* gets the brief's
  path. The brief's own words stay in the brief.
- **The card.** For 10 minutes after it lends, the card says *Read for: <meeting>* and the pages
  named, as today; the Calendar's line for the meeting says *from the Wiki: 2 to discuss · 3 pages*
  once the brief is back.

The demo's Meetings orkspace (`demo/meetings.py`) shows it: a quick note before the mail arrives
ends up in Alex's brief.

## 7. Finding

- `wiki.relevant` works for any script: words are Unicode letters (`\w` without digits and `_`),
  compared by a stem of their first 5 letters, so *Сергеем* finds *Сергей*. Titles and `aliases`
  count three times as much as the text.
- A **search** field over the tree in the window: titles, aliases and text, as typed, no model; the
  hits show as the tree does (a click opens the page).

## 8. Checking: the quality check

The librarian answers for the wiki's quality, on a schedule, and says what it found.

- **When.** `config.check`: `weekly` (default, Monday at `day_starts` or 09:00), `daily`,
  `ingest` (after each take-in) or `off`. *Check now* in the window, as *Check the wiki* is today.
  Each check is a `lint` job with its cost in the job log.
- **Rules every refresh (no model):** a relative link to a file that is not there; a page missing
  from its section's `index.md`, or listed and missing; a page without front matter or without
  `kind`; a meeting page whose meeting is gone from the Calendar. These need no agent and show at once.
- **The agent weekly:** contradictions, stale facts, orphans, topics with no page — the lint prompt
  as today, with one change: each problem line is written as `- [kind] page — what to do`
  (`kind` one of `structure`, `link`, `contradiction`, `orphan`, `stale`, `missing`), so the window
  can count them. It may fix indexes and links itself, as today; nothing else.
- **What shows.** The window: a strip *Quality check found 4 problems · checked Mon 09:04* with
  **Fix links and indexes**; a Quality block with the schedule, the next check and the last cost,
  a count per kind and the list (page, problem, fix). The card: `⚠ 4 quality problems` while any is
  open. Fixed problems leave the list at the next check.
- `wiki.linted` carries the counts; a Horn or the Task board can listen to it.

## 9. Settings

| Key | Default | What |
|---|---|---|
| `inbox` | `notes/inbox` | where Quick notes are written (a source of the wiki) |
| `calendar` | the only War Drum | the Calendar meetings are matched in |
| `check` | `weekly` | the quality check: `weekly`, `daily`, `ingest`, `off` |
| `suggest_model` | on | ask the light model when rules find nothing |

## 10. Where the code goes

- `realm/quicknote.py` (new, pure): the note's front matter (write, read), the rules that suggest
  (when, who, meeting, section, tags, links), the light model's prompt and its parse.
- `realm/wiki.py`: Unicode `relevant`, the `meetings` and `people` sections, the agenda block
  (write, tick, move back), meeting pages by id, the lint line format and its parse, the rule checks.
- `realm/daybook.py`: weekdays and Russian day words in `parse_when`.
- `core/workers/scrolls.py`: `note()`, the inbox in the sources, binding on `refresh`, `lend` by
  meeting id, the check's schedule, `wiki.noted`.
- `realm/catalog.py`: the action `wiki.note`, the event `wiki.noted`, the settings of §9.
- `gui/views/scrolls.py` and `js/buildings/scrolls.js` (+ css): the Quick note panel, the Quality
  block, the search field, the card's lines. `js/warchief.js`: `/note`. `gui/views/fields.py` and
  `js/buildings/fields.js`: **→ Wiki** on a note.
- No TUI work (it is deprecated). Tests next to each: `tests/test_quicknote.py`, and the Wiki's,
  Calendar's and Task board's tests grow.

## 11. Stages

1. **Quick note**: the panel, the file, the inbox, `/note`, **→ Wiki** on the Task board; rules-only
   suggestions with Unicode `relevant`.
2. **Meetings**: binding to the Calendar, the agenda block, open items, `lend` by meeting id, after
   the meeting.
3. **Quality check**: the schedule, the rule checks, the lint line format, the window's block, the card.
4. **Search**, and the light model's suggestions.

Not planned: reading attendees from `.ics` (`ATTENDEE` lines) — a later step that makes *Who* and
*Meeting* match better; syncing people from Slack or mail.

## 12. As built

- **Calendars.** The Wiki reads every War Drum in the town (`calendar` names one to read only it),
  not "the only one": a town often has several.
- **Who.** Besides the people the wiki has pages for, a capitalised name in the note that a meeting's
  title says too (*Ann* → *1:1 with Ann*) counts as a person for matching.
- **Open items** stay in the Wiki's window (*To discuss → Open items*) until a meeting with the
  person comes; the worker writes no lines into people's pages (the librarian may, at take-in, as
  `WIKI.md` says).
- **Code.** `realm/quicknote.py` (the note), `realm/agenda.py` (meetings, days, people, the page),
  `realm/wikicheck.py` (the quality check), `realm/wikifind.py` (search, the light model);
  `core/workers/scrolls_meetings.py` and `scrolls_quality.py` are parts of the Wiki's worker.
- **The Calendar's line.** The War Drum's view reads, by meet id, what each Wiki that reads it keeps
  (`kept_for`: the items not ticked off, the pages the notes link); nothing is sent for it, and a Wiki
  whose agenda changed asks the Calendars it reads to draw again. The window says *from the Wiki: 2 to
  discuss* beside the meeting (*· 3 pages* once its brief is back); the closed card, narrow, a pill
  *✎ 2* with the words on hover.
- **`/note` in the Warchief bar.** The suggestions stand over the bar as the text is typed (after
  400 ms, as the panel's): the meeting, the section, the tags, the pages to link. Tab walks the coming
  meetings (the next 14 days, the suggested one first; `suggest` returns them as `meetings`) and *Not
  for a meeting*, Shift+Tab back; Enter saves what is shown. `@Wiki` names the wiki, as any `@name`.
  The bar has no ✕ per tag or link: what it should not keep is dropped in the Wiki's own Quick note.
- **Tests.** `test_quicknote.py`, `test_wiki_meetings.py`, `test_wiki_quality.py`, `test_wiki_find.py`;
  the bar's `/note` in `test_gui_browser.py`.
