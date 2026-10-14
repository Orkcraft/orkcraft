# Design — an ork's face says its role

Status: decided 2026-10-12 with the owner; nothing drawn. Priority **P1**, after the Town Hall's roles are folded
([town-hall-roles.md](town-hall-roles.md)): drawing eleven faces and folding them to eight would waste three. Builds
on [ork-console.md](ork-console.md) §2 (an ork is a role), [sprites.md](sprites.md) (the ork's head and its states),
[select-a-building.md](select-a-building.md) §2 (the hats), `tools/hat_sprites.py`, `js/icons.js` `HATS`.

## 1. Why

Today an ork's face is the one head under a hat chosen by its **building**: six hats for twenty types (`js/icons.js`
`HATS`), grouped loosely (Metrics and Sound alerts wear the lookout's hat, the Router the clerk's). The owner's word:
made at random, they say little. Since an ork is a role ([ork-console.md](ork-console.md) §2), its face should say
the **role**: the same face wherever that role works, a different one for a different expertise.

## 2. The rules

1. **The face is the role's, never the building's.** The Mechanic looks the same on the Test bench, on the night's
   council and in the ork slots list. Two roles never share a face.
2. **The head stays one; the headgear and at most one held thing say the expertise.** The house head
   ([sprites.md](sprites.md)) carries the camp's look; what it wears tells the roles apart.
3. **It reads at 16 px and in grey.** The test: the eight Town Hall roles told apart at badge size with the colour
   taken out. A silhouette that needs colour to be told apart is redrawn.
4. **A face never says a state.** The state stands beside the head, as today ([sprites.md](sprites.md): a mark
   inside a 24×16 head could not be told apart), and is the one status of [ork-console.md](ork-console.md) §5. Who the
   ork is and what it is doing are two signs.
5. **A persona is a badge, not a face.** The Agent pool's Grunts by topic (tests, frontend) keep the Grunt's face
   with a small topic badge. One face per role, not one per persona, or the faces never end.
6. **Office draws no sprite;** it says the role's name in words where Camp shows the face (today it says "Agent").
7. **A custom role** keeps the bare head (the Peon) until it is given a face. Drawing one for it is Later.

## 3. Which faces, in what order

Only roles that call a model get a face ([yards.md](yards.md): an ork lives only where a model thinks), and only
roles that are on the town by default ([catalog-shelves.md](catalog-shelves.md)) come first.

**First: the Town Hall's eight** ([town-hall-roles.md](town-hall-roles.md) §4), with a starting idea for each:

| role | expertise | headgear and held thing (a starting idea) |
|---|---|---|
| Warchief | the lead | the crown (as today) |
| Mason | data, schemas, scripts | a mason's cap, a trowel |
| Alchemist | UI/UX | a beret, a flask |
| Mechanic | quality on cases | goggles, a wrench |
| Treasurer | money and limits | a coin-trimmed hood, a coin purse |
| Farseer | what the person needs | a hood with an eye |
| Warder | safety | a shield helm |
| Pathfinder | the town's layout and roads | a scout's hood, a compass |

**Then: the core's orks that think**, by the catalog's `agentic` types on the core shelf: the **Grunt** (Agent pool)
and the **Quartermaster** (Review gate).

**Then, as their shelf is turned on:** Chieftain (Review board), Prospector (Research), Bard (Audio briefing), Smith
(Branches & PRs), and the stewards that come to a yard when woken.

## 4. What changes in the code (when built)

- `js/icons.js` `HATS` maps a **role** to its headgear, not a building type to a hat; a building's steward shows its
  role's face.
- `tools/hat_sprites.py` draws the role's headgear and held thing on the house head, at the sizes it makes today.
- The old hats' names stay loadable where a setting or a town names them (CLAUDE.md, Wording).
