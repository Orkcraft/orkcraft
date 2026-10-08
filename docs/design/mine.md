# Design — the Mine: deep research, checked by more than one mind

Status: written 2026-10-08; nothing built yet. Stage 0 (§12) checks the tools before anything is
built. Builds on the AI tools' registry and its `web` flag ([harnesses.md](harnesses.md)), the Wiki's
inbox ([wiki-librarian.md](wiki-librarian.md) §4), the Calendar's timeline (`realm/drumbeat.py`), the
Agent pool's kinds of work ([barracks-flows.md](barracks-flows.md)), Answers and the Review board
([review-board.md](review-board.md)), and the flat sprite set ([building-sprites.md](building-sprites.md)).

## 1. Why

Claude, ChatGPT and Antigravity each have a research mode: one model searches, reads, writes a report.
It is fast and often good, but it is **one mind**: what it got wrong it got wrong with confidence, and
nothing in the report says which line rests on one blog post and which on five independent sources.

The town leads several AI tools. Three of them can search the web from a reading run (Claude Code,
Codex, Hermes: `web=True` in `harnesses.REGISTRY`). The Mine puts them on the same question
**independently** and keeps only what they agree on, with sources they did not share. Where they
disagree, it digs again: more sources first, then a debate, and last the person decides.

The aim is the best-checked research the town can make, not the cheapest or the fastest. What the
Mine is for and what it is not:

- **For:** deep research on the open web — a market, a technology, a law, a choice between products,
  a question with many sources that disagree.
- **Not for:** the town's own knowledge (Confluence, Notion, the repository). Those go through an
  Agent pool reading them, or the Wiki, as today. The Mine has no source list of its own.
- **Not a copy of a vendor's research mode.** It does not crawl, index or call a vendor's closed
  research mode. Its value is the cross-check, the sources kept in the Wiki, the cost it is held to
  and the repeat on a schedule that the person sees.

## 2. Wording

New entries in `realm/lexicon.py` `TERMS`:

| key | word | Camp word (`was`) | what |
|---|---|---|---|
| `mine` | **Research** | The Mine | the building type (`_ALSO`: *Mine*) |
| `orc.mine` | **Researcher** | Prospector | the ork that searches with one tool |
| `finding` | **Finding**, *Findings* | | one claim of a report, with its sources |
| `confirmed` | **Confirmed** | | a finding the check passed (§5) |
| `disputed` | **Disputed** | | a finding the tools disagree on |
| `single` | **One source** | | a finding only one tool or one site gave |
| `dig_round` | **Round**, *Rounds* | | one pass of search over the open findings |

`claim` is taken (*Area in work*), so a report's lines are **findings**. Labels say plainly what
happens and what it costs: *Start research · up to $3.00*, *Search more*, *Accept this one*,
*Keep it disputed*. The Researcher's lines may joke; the money and the verdicts never do.

## 3. What goes in

| Where | How |
|---|---|
| The Mine's window | **New research**: the question, optional *Must cover* (sub-questions) and *Skip* (sites or topics); the limit for this one, the tools it uses (§10 defaults) |
| The Warchief bar | `/research <question>` (`@Mine` names one when the town has several) |
| A road | any cart: its title is the question, its text the brief (a Task board card, a Router rule, a Calendar beat). Its `ref` stays, so the report can go back by a return road |
| A repeat | §8: only through the Calendar |

Before anything runs the window shows the plan's cost range (*about $1.20–2.80, limit $3.00*). A cart
by a road starts at once within the building's limits.

## 4. The cycle

```
plan ─▶ search (each tool alone) ─▶ check ─┬─▶ report
                                           │
            ┌──── open findings ◀──────────┘
            ▼
   round 1: search more ─▶ check ─▶ round 2: debate ─▶ check ─▶ still disputed → the person (§6)
```

1. **Plan** — one call on the main tool, no web: the question cut into 3–7 sub-questions, each with
   what would answer it. Shown in the window as it is made; the person may edit it while search runs.
2. **Search** — one Researcher per tool (`read` mode with `web=True`, an empty folder, no repository).
   Each gets the plan and nothing the others found. Each answers JSON: findings, each with its
   sources (URL, title, date, the quoted line) and how sure it is.
3. **Check** (§5) — by rules first, then one call to group findings that say the same thing.
4. **Rounds over what is open** — a finding that is *Disputed* or *One source*:
   - **Search more** — each tool gets only the open findings and is asked for sources it did not use
     (the domains already seen are named). A tool that gave nothing may be swapped for another.
   - **Debate** — each tool sees the others' findings *with their sources* and answers per finding:
     keep, change, or withdraw, and why. A finding that every side now holds, with independent
     sources, is confirmed; the rest stays open.
5. **Stop** when every finding of a sub-question is confirmed or the person has decided on it, or
   the limit in money is reached, or `rounds` (default 3) are done. A stop by limit says so on top of
   the report: *Stopped at the limit: 2 findings still disputed*.

## 5. The check: what *Confirmed* means

A finding is **Confirmed** when:

- at least **two different models** give it — models, not tools: Hermes or pi on a Claude model is
  the same mind as Claude Code (`harnesses.model_on`, and the model each run reports), and
- its sources come from at least **two different domains**, and
- those sources are not one text copied: the same quoted line on two sites, or a page that cites the
  other, counts once (rules: the quote, the canonical link, a `source:`/`via` line).

Otherwise it is **Disputed** (the tools say different things) or **One source**. Rules do what they
can without a model: domains, dates, dead links (a source that does not open is dropped and said),
the quoted line found on its page. One light call groups the findings that say the same thing in
other words. Nothing a page says can change the check: a page that writes "this is confirmed by X"
is a page with that text in it.

## 6. The person decides what stays disputed

When the rounds end with findings still disputed, the Mine asks **in Answers** (🔥), one question per
finding, with both sides and their sources:

> **Disputed:** *Acme's free tier ends on 1 March.*
> Claude, Codex: yes (acme.com/pricing, a news site, Jan) · Hermes: it ends for new accounts only
> (acme.com/blog, Feb)
> **Search more · Accept: Aug 2025 · Accept: Aug 2026 · Keep it disputed**

- *Search more* runs one more round on this finding only, within the limit (or asks to raise it).
- *Accept* marks it **Confirmed by you**; the report says who decided.
- *Keep it disputed* puts both sides in the report under **Disputed**.
- The report waits for the answers, up to `wait_answers` (default 3 days); then it goes out with the
  unanswered findings as disputed. A disputed finding is never written as confirmed.

The Mine's autonomy does not apply here: deciding a fact is the person's, whatever the Freedom.

## 7. What comes out

- **The report** — Markdown: the answer in short, then per sub-question its findings, each marked
  ✓ / ⚠ / ①, its sources numbered, the disputes with both sides, and a table: tools, models, sources
  per tool, rounds, cost.
- **To the Wiki** — the report goes to the Wiki's inbox as a note (`kind: research`, `question:`,
  `asked:`, `sources:`, `confirmed:`, `disputed:`), the `want: know` of
  [barracks-flows.md](barracks-flows.md) §3. The librarian takes it in as any note: the findings become
  pages, the sources stay linked, the Quality check sees them. Without a Wiki the report stays in the
  Mine (`.orkcraft/mine/<id>.md`) and opens in the panel.
- **Back by the road** — a cart that came with a `ref` gets the report back, so a Task board card or a
  Calendar beat shows it.
- **On the bus** — `mine.reported` (the report's path, the counts), `mine.asked` (a dispute for the
  person). A Horn or the Task board can listen.

## 8. Repeats: only through the Calendar

A repeated research is never a hidden timer. The person sets *Repeat* on a research (in the Mine's
window or as *+ Repeat* on the Calendar), and it shows on the Calendar's timeline as a schedule beat
(↻, `drumbeat.jobs` reads the Mine's repeats the way it reads a Workshop's `schedule`), with its
limit as its detail (*Weekly · ≤ $3.00*). A town with no Calendar cannot set a repeat; the window says
to build one.

A repeat runs the same plan again and writes **what changed**: new findings, findings that went
from confirmed to disputed, sources gone. Nothing changed: a one-line report, and the Wiki gets no
new note.

## 9. What the person sees

- **The card**: the question in work, its round, and the sources per tool in the tools' own marks and
  colours (`harnesses` `mark`, design tokens `harness-<id>`): `✻ 14 · ◎ 9 · ☤ 11 · ✓ 23 · ⚠ 2 · $1.40`.
  Idle: the last report's title and its counts.
- **The window's Work**: the plan with each sub-question's state; a column per tool with what it
  found so far; the findings with their marks; the disputes waiting on the person; the cost against
  the limit. Past reports below, newest first.
- **Info**: as every building — the steward, the roads, the garrison (one Researcher per tool).
- **The sprite**: a mine entrance in the flat set (§11).

## 10. Settings

| Key | Default | What |
|---|---|---|
| `tools` | every tool on with `web` | the tools that search; with only one, the Mine warns that nothing can be confirmed |
| `limit` | `$3.00` | the most one research may spend; a research may lower it, never raise it past `month_limit` |
| `month_limit` | `$30.00` | the most the Mine spends in a month, repeats included |
| `rounds` | `3` | rounds after the first search |
| `min_models` | `2` | different models a confirmed finding needs |
| `min_domains` | `2` | different domains its sources need |
| `wait_answers` | `3d` | how long a report waits for the person's decisions |
| `wiki` | the only Wiki | where reports go (`""`: kept in the Mine) |

The spend goes to the side ledger with the purpose `research` ([simplify.md](simplify.md) §2).

## 11. The sprite

A sheet of the flat set (`building-sprites.md`): a low mine entrance — a timber frame in a hillside,
a dark opening, a cart rail coming out; ivory tusks as the frame's finials; one gold accent: a lamp
over the opening (or a nugget in the cart). Drawn by an image model with the set's prompt and the
existing headers as reference, then cut with `tools/sheet.py` into
`design-system/sprites/buildings/mine/header.png`. The catalog entry: size **M**, `⛏️`.

## 12. Stages

0. **Check the tools**: can agy's reading run search the web (today its `read` drops `web`)? Which
   model each tool reports per run, so §5 can count models? A research run on each tool: its JSON,
   its cost, how often a source does not open.
1. **One question, one round**: the building, `TERMS`, the sprite, the plan, the search on every
   tool, the check by rules, the report in the Mine; the card's counts.
2. **Rounds and disputes**: search more, the debate, the questions in Answers, the stop by limit.
3. **Out**: the Wiki's inbox, the return road, `mine.reported`; `/research`.
4. **Repeats** through the Calendar, with what changed.

No TUI work: it is deprecated.

## 13. Where the code goes

- `realm/research.py` (new, pure): the plan's prompt and parse, a finding and its sources, the check
  of §5 (models, domains, copies), what changed between two reports, the report's Markdown.
- `core/workers/mine.py` (new): the cycle, the rounds, the limits, Answers, the bus events; the
  Wiki's inbox through the Wiki's worker (`note`).
- `realm/catalog.py`: the type `mine`, its events, its settings. `realm/drumbeat.py`: the Mine's
  repeats in `jobs`. `realm/lexicon.py`: §2.
- `gui/views/mine.py`, `js/buildings/mine.js` (+ css): the card, the window. `js/warchief.js`:
  `/research`.
- Tests: `tests/test_research.py` (the check above all: two tools on one model, one text on two
  sites), the worker's, the Calendar's.

## 14. Open questions

- Should the plan wait for the person's yes before search starts (a research is up to $3)? This
  design says no for the window (the cost is shown before Start) and no for a road (the limits hold).
- Two tools on the same model: drop one from the search, or keep it and count it once? Counting once
  is safe; dropping saves money.
- Sites behind a login or a paywall: a source the tool could not read is not a source. Should the
  person be able to add a page by hand to a dispute?
