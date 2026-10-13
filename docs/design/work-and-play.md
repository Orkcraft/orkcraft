# Design — two looks, two times of day: Office at work, Camp as the game

Status: proposal 2026-10-13, the owner's hypothesis; nothing built. Priorities in §5. Builds on
[portrait.md](portrait.md) §3 (the two looks), [color-pass.md](color-pass.md) (pixels stay; quiet ground, loud
signals), [first-mission.md](first-mission.md) (the campaign), [the-score.md](the-score.md), CLAUDE.md (Wording: one
vocabulary, two looks).

## 1. The hypothesis

> **A person works in Office during working hours, and after work comes back to Camp as to a game, to improve the
> town.**

So each look gets a job. Today Office is "the calm look for whoever thinks it is a toy". With this, the looks become
two ways of using Orkcraft:

| | Office | Camp |
|---|---|---|
| when | working hours | after work |
| what for | a control room: dense, numbers, text, fast | the game: missions, the score, 💡, making the town better |
| feels like | a tool | Warcraft II's and Stardew Valley's kind of world, in pixels |

This also settles how dense Camp should be: it can be more game and less diagram, because Office holds the numbers.

## 2. The rules that hold

1. **A look changes only how things are drawn, never a word** (CLAUDE.md). Camp does not hide information; **it
   draws it as things**, and the exact number is always on the mouse.
2. **One layout, two drawings,** never two interfaces: the same elements in the same places, each drawn as a number
   in Office and as a thing in Camp ([color-pass.md](color-pass.md): Office is tokens and words only).
3. **The signals are the same in both:** 🔥, ❓, an error, a held task ([ork-console.md](ork-console.md) §5).

**The table of drawings** (to be finished element by element, P1):

| element | Office | Camp |
|---|---|---|
| spend | `$1.21 / $5` or `34 % of the window` | a pile of coins at the Town Hall, growing |
| a cart's load | `12k tokens` | the heap on the cart |
| a building's queue | `To Do 3` | crates in its yard |
| an ork's state | a word: Thinking, Running pytest, Asks | the ork's pose and motion, its bubble |
| the score's trend | `−12 % per result` | the mascot's mood; a banner on a lean week |
| a building's level | `Level II` | its flag and footing ([growth.md](growth.md)) |

## 3. Camp, more world than diagram

Toward Warcraft II and Stardew Valley, keeping the pixels ([color-pass.md](color-pass.md) §7):

- **At the map and overview zooms, a world:** textured ground, buildings larger, roads as paths, carts driving and
  orks walking on them, a little life (smoke, birds, the mill turning). **Data cards only at the close zoom or on
  selection.**
- **The yard as ground with a light fence** ([color-pass.md](color-pass.md) §6), the juice of arrivals and answers
  (§7 there).

## 4. Switching

- **One key** switches the look, as today in Settings, and the choice is remembered per machine.
- **Later:** a soft offer at the end of the person's working day ("the day is done; a look at the camp?").
- **The working hours are asked when they are needed, not in the onboarding** (decided 2026-10-13): before the first
  quest only the class and the AI tools are asked ([first-mission.md](first-mission.md) §2), and every other question
  pushes the first win away. They are asked at the first of:
  1. **Mission 2**, which is about time and the clock's dial: "When is your working day?", 10–19 by default, the quiet
     hours beside it;
  2. **the person switching to Camp by hand after hours:** once, "Done at 19:00? I will offer the camp after work",
     one press to confirm;
  3. **a guess offered, never made silently:** after a week the town knows the hours the person is around
     (`realm/awake.py`) and asks "you seem to work 10–19, right?".

  Until they are set there is no offer, only the key.
- **Mission 1 is played in Camp:** it is the game's first mission.

## 5. Priorities and how we know

- **P0 before the launch:** Camp at the map and overview zooms with no cards: the living town. It is the frame of the
  demo GIF, and "it is a game" is the hook.
- **P1:** the table of drawings, element by element; the yard as ground; the juice.
- **Later:** the offer to switch at the end of the working day.

**How we know** (the local event log, [dogfood-logs.md](dogfood-logs.md)): which look is on at which hours; where the
💡 items are applied and the missions played, in Camp after work or not. If people never switch, the looks stay what
they were: a matter of taste.
