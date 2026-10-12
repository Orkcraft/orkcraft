# Design — the town's time: every schedule on the sun and moon dial, work that waits for a limit

Status: proposal 2026-10-12, talked through with the owner (§4 and §5 decided); nothing built. Priority **P1**, first of the P1s: it
speaks to the people Orkcraft is for, who work on a subscription through their own AI tools and meet its limits
every day. Builds on [building-views.md](building-views.md) (the Calendar's beats: meetings, scheduled runs,
≈ limits), [calendar-import.md](calendar-import.md), [codex-limits.md](codex-limits.md) (a window's `resetsAt`),
[catalog-shelves.md](catalog-shelves.md).

## 1. What is there and what is missing

Today the Calendar building draws three kinds of beat on its strip: meetings, scheduled runs and an estimate of when a
limit runs out ([building-views.md](building-views.md), `beats`). What it does not do:

- show **every** schedule of the town: the night's council, External listeners' schedules, Metrics' refresh
  ([catalog-shelves.md](catalog-shelves.md) §3a), deferred tasks;
- let the person **act** on one: run now, pause, move;
- hold work **until a limit resets** and start it then.

## 2. The rule: one place to see time

> **A schedule is set where it belongs; every schedule in the town is seen and steered on the town's clock** (the
> HUD's sun and moon dial and its time strip, §5).

A building keeps its own cadence (Metrics hourly, a listener's schedule, the night's council at 04:40). The clock
does not own them; it shows them all on one strip and steers them: **Run now**, **Pause**, **Move**. A schedule that
is nowhere on the strip is a bug.

## 3. Limits on the strip

Each AI tool's windows, where it tells them (Codex's `resetsAt`; Claude Code's and agy's as they can be read):

- the estimate of when a window runs out at today's pace, and when it resets, as beats on the strip;
- a burst of work planned near a reset, or past an estimated run-out, said plainly on the beat.

## 4. Work that waits for a reset

**Run at the reset:** a task or a run can be put off until a window resets, and starts by itself then. The time
strip shows it on the reset's beat; the ork slots list ([ork-console.md](ork-console.md) §8) shows it as waiting, taking no
slot.

**The town holds work by itself** (decided 2026-10-12), never out of sight:

- work that would start with a window spent, or spend the rest of it, is **held** until the reset;
- **the Treasurer signs every hold** (money and limits are its expertise, [town-hall-roles.md](town-hall-roles.md)):
  "held by the Treasurer until the 14:00 reset". A rule in code, so no session and no slot;
- every held task carries a plain mark where it is shown (its building, the ork slots list, the clock's strip) and
  **Run anyway**, which starts it now and says what it will spend of the window;
- the morning brief names what was held and what ran at the reset.

## 5. The town's time is not a building: the sun and moon dial

Decided 2026-10-12, the owner's idea (Warcraft III's day and night clock). The town's time is the whole town's, like
🪙 and 🥩, so it lives in the HUD, not on the map. The dial in the middle of the HUD (`js/chrome.js` `Hour`) already
shows the hour as a sun or a moon, and Do not disturb is proposed for it ([select-a-building.md](select-a-building.md)
§5): one place answers "what will the town do, and when will it bother me".

- **The dial:** the sun for the person's hours, the moon for the quiet ones (the night round, the Elders, held work
  that runs at night); a small mark for the next beat and for a coming reset; the number of held tasks. No more: the
  dial stays a glance.
- **A click opens the time strip:** every schedule (§2) with Run now, Pause, Move; each AI tool's windows (§3); held
  work (§4) with Run anyway.
- **The Calendar building keeps the person's meetings only:** imported calendars, meeting documents, preparing for a
  meeting. The More shelf ([catalog-shelves.md](catalog-shelves.md)). Its beats of scheduled runs and limits move to
  the dial's strip.
