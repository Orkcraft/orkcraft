# Design — a process as a line: BMAD and other staged processes in the camp

Status: design, 15 October 2026 (the owner and the PM). Priority **medium (P1)**: BMAD is a common way of working for
the first audience (developers building their own products with agents). Built after the testers' first feedback,
as a ready **line template** (Mission 2's "a process that comes back" and the packs by kind of user). Builds on
decisions-2026-10.md §20 (the lines), design-system-v3.md §4 (stations, annexes), ork-console.md §14 (the pool's
lanes as roles).

## 1. One process, one line; a stage is a station, not a line

A staged process gets **one line of the person's quarter** (line 2 and on). Its stages are **stations along that
line, left to right in the process's order**; a task's cart rolls east and stops at each one, which loads its
result into the cart (the brief, the PRD, the architecture, the stories). The waybill lists every stage with its
cost. No stage has a track of its own.

```
 line 2 «BMAD» │ ═▶ Analyst ═▶ PM ═▶ UX ═▶ Architect ═▶ Scrum master ═▶ [ depot: dev ] ═▶ QA ═▶ … to the Review gate
               │     brief      PRD    design  architecture   stories ✂        parallel bays     tests
               │       🔥⛺      🔥⛺            🔥⛺              ▮ barrier       ▮ barrier
```

## 2. Several depots on one line? No: role huts, and at most one depot

- **The early stages are one ork each:** a **role hut**, a small building holding one ork of that role (Analyst,
  PM, UX designer, Architect, Scrum master: the Agent pool's lanes as roles, ork-console.md §14, given a hut each on
  the line). They need no parallel bays, so they are drawn small; the line stays short (eight places hold it).
- **The depot appears once, where parallel work happens:** the implementation, where the Scrum master's stories run
  side by side in its bays. A process without parallel work has no depot of its own and uses line 1's.
- **The split:** at the Scrum master's hut one epic cart arrives and **several story carts leave**, each with its own
  id and its parent on its waybill; they queue at the depot.

## 3. Debates after a stage: an annex, not another building

"I want debates after every stage" is a **property of a station**, drawn as its **council annex**: a small ring of
logs with a fire beside the hut (the growth annexes' place, design-system-v3 §4.12). With it on, the stage's result
is argued by two or three critic roles (the Review board's members, reused) **in place** before the cart moves on;
the fire burns while they argue; the verdict and the debate's cost are rows on the waybill. No detour to a Review
board building, no second track.

- Turned on per station in its settings, or **"Debate after every stage"** on the line at once.
- **Its price is said when turned on:** an estimate per cart ("about 3 critics × 4 stages: ~$0.40 or ~6 % of the
  window per task"), since debates multiply the runs.
- **The template's default:** debates after the PRD and the architecture only (BMAD's two key documents), off
  elsewhere.

## 4. The person's approvals: a barrier on the line

Where the process wants the person's yes (BMAD: the brief, the PRD, the architecture), a **barrier** stands on the
line after the station (the Review gate's own barrier, small): the cart waits with the yellow flag; the person reads
the document in the waybill and lifts the barrier, or sends it back with a note (it goes round to that station
again). The Review gate on line 0.5 stays the last check for what leaves the camp.

## 5. What it reuses and what is new

- **Reused:** the stations' stops, one-way travel, the waybill, the pool's roles, the Review board's members, the
  Review gate's barrier, the depot's bays, the round's price.
- **New:** the role hut (one small sprite, an ork at a desk; a sign with the role); the council annex (a small
  campfire ring, from the old Review board art); the line barrier; the split of one cart into several; the line
  template (a data file: stations, their roles and prompts, debates, barriers), installed by one button.
- **Size:** about 4–6 days of code plus one small art sheet; the template's prompts follow BMAD's published roles.

## 6. Open

1. Do UX and architecture run in parallel (the cart splits in two and joins again) or one after the other? The
   template starts sequential (simpler), parallel later if the testers ask.
2. BMAD's own files (its agents' prompts, its folder layout in the repository): read and followed, or Orkline's own
   roles with BMAD's names? To be checked against BMAD's current version before building.
