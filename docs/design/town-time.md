# Design — the town's time: every schedule on the Calendar, work that waits for a limit

Status: proposal 2026-10-12, talked through with the owner; nothing built. Priority **P1**, first of the P1s: it
speaks to the people Orkcraft is for, who work on a subscription through their own AI tools and meet its limits
every day. Builds on [building-views.md](building-views.md) (the Calendar's beats: meetings, scheduled runs,
≈ limits), [calendar-import.md](calendar-import.md), [codex-limits.md](codex-limits.md) (a window's `resetsAt`),
[catalog-shelves.md](catalog-shelves.md).

## 1. What is there and what is missing

The Calendar already draws three kinds of beat on its strip: meetings, scheduled runs and an estimate of when a
limit runs out ([building-views.md](building-views.md), `beats`). What it does not do:

- show **every** schedule of the town: the night's council, External listeners' schedules, Metrics' refresh
  ([catalog-shelves.md](catalog-shelves.md) §3a), deferred tasks;
- let the person **act** on one: run now, pause, move;
- hold work **until a limit resets** and start it then.

## 2. The rule: one place to see time

> **A schedule is set where it belongs; every schedule in the town is seen and steered on the Calendar.**

A building keeps its own cadence (Metrics hourly, a listener's schedule, the night's council at 04:40). The Calendar
does not own them; it shows them all on one strip and steers them: **Run now**, **Pause**, **Move**. A schedule that
is nowhere on the Calendar is a bug.

## 3. Limits on the strip

Each AI tool's windows, where it tells them (Codex's `resetsAt`; Claude Code's and agy's as they can be read):

- the estimate of when a window runs out at today's pace, and when it resets, as beats on the strip;
- a burst of work planned near a reset, or past an estimated run-out, said plainly on the beat.

## 4. Work that waits for a reset

**Run at the reset:** a task or a run can be put off until a window resets, and starts by itself then. The Calendar
shows it on the reset's beat; the ork slots list ([ork-console.md](ork-console.md) §8) shows it as waiting, taking no
slot.

Open question for the owner: **who defers?**

1. only the person, by hand ("run this when the limit resets");
2. the town too: work that would start with the window spent is held by itself and shown as held, with Run anyway.

The second saves the most and surprises the most; under the rule of [ork-console.md](ork-console.md) §1 (nothing out
of sight) it needs a plain mark on every held task.

## 5. Two things under one name

The Calendar is two things, and the shelves treat them apart ([catalog-shelves.md](catalog-shelves.md)):

- **the town's time** (§2–4): schedules, limits, deferred work. Every person who runs agents needs it;
- **the person's meetings** (imported calendars, meeting documents, preparing for a meeting): for a person whose day
  is meetings, as the owner's is. The More shelf.

Whether they stay one building with two kinds of beat (as today, `beats`) or split is for after the testers.
