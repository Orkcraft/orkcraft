# Design — products with the same first idea: agents as characters in a game world

Status: looked at 2026-10-13 at the owner's ask. They share Orkline's starting idea, to make working with AI agents
feel like a game, and in the owner's words "did not go deep technically". Read from their public pages; none was
installed. Builds on [audience.md](audience.md) §3 (the story), [decisions-2026-10.md](decisions-2026-10.md) §4 (the
risks), [open-questions.md](open-questions.md) Q16 (the hooks).

## 1. What was found

| product | what it is | AI tools | how it knows state | acts on the agents? | reach |
|---|---|---|---|---|---|
| [Pixel Agents](https://github.com/pixel-agents-hq/pixel-agents) | the person's agents as pixel characters in a small office: they type when editing, read when searching, a bubble when waiting; a layout editor, asset packs, sub-agents shown | Claude Code only; Codex, Gemini, Cursor on the roadmap | Claude Code hooks, transcripts as a fallback; changes nothing in Claude Code | no: it shows; the VS Code extension opens terminals | **about 9.7k stars**, MIT; VS Code extension and `npx pixel-agents` |
| [AgentVille](https://github.com/StrSimon/AgentVille) | "mission control" as an isometric dwarf village; a building per kind of work (Forge for edits, Arena for tests, Mine for installs); dwarves needing input walk to the Town Hall | Claude Code, Codex | hooks into both, a local bridge; cost and tokens from transcripts; the 5-hour and weekly limits (Claude's read by wrapping its status line) | answers permissions and questions, sends orders on the next tool call | 1 star, MIT; desktop app and `npx` |
| [Agent Village](https://github.com/diwakersurya/agent-village) | agents as 3D characters, an office view and a village view (tools as buildings), status beacons, sound | Claude Code, Codex, Gemini CLI | tagged hooks into all three, failing open; logs and a process scan without hooks | answers questions and permissions from the browser | 0 stars, MIT, macOS |
| [Claude Pixel Village](https://github.com/Sergb39/ClaudePixelVillage), [Agentville](https://github.com/Dimural/agentville) | the same idea, smaller: sessions as adventurers or pixel characters animated by what they do | Claude Code | a Claude Code plugin; the session | no | small |
| agentvillage.app | **not read:** unreachable from here (DNS and the network policy). The name is also used by unrelated research projects (AI Digest's AI Village, an Edge Esmeralda experiment) | — | — | — | the owner to check |

## 2. What it means

1. **The category exists and is crowded.** At least five projects in a year put the person's agent sessions in a
   pixel world. "Agents as characters" is no longer a difference; **it is the category's ticket**.
2. **The demand is proven.** Pixel Agents' ~9.7k stars, for a view that changes nothing, says people want to *see*
   their agents. It is good news for the GIF, and a warning: what wins attention is how cheap the first look is.
3. **They all watch sessions; none runs the work.** Each one draws sessions the person started elsewhere: `htop` as
   a game. **Orkline's work is the factory around the sessions:** carts with one id for life, roads between
   buildings, the Review gate, the score per result, roles, missions. Their building means a kind of tool call;
   **ours means a step of a flow**.
4. **The gap closes from their side.** Pixel Agents' roadmap: every AI tool, then "a true game" (limits and budget
   as health bars, scores), then orkestration (orchestrator characters, teams, handing off work, agents taking tasks
   from a board), with ~10k stars of reach behind it. AgentVille already has an inbox and orders. **Time matters:**
   beside the platforms of [decisions-2026-10.md](decisions-2026-10.md) §4.3, this is the second pressure, from below.

**Their community, seen 2026-10-13:** Pixel Agents' Discord has **155 members, 25 online**, against ~9.7k stars.
Stars came from a GIF that spread; a community did not come with them (about 1.6 % of the stars). So:

- **The community place is still open:** no project of the category has a lively one yet. The owner's goal
  ([decisions-2026-10.md](decisions-2026-10.md) §4.4) is reachable, and it is where Orkline can lead, not follow.
- **Stars are not the measure;** people who come back and talk are ([launch-prep.md](launch-prep.md) §4).
- **Their Discord is free research:** what its people ask for (more AI tools, handing work on, a board, limits) is
  what this audience wants next. The owner joins as a user, reads, **never promotes Orkline there**.

**Their reach, from their README's badges (2026-10-13):** version 1.4.1, **126k installs from the editor
marketplaces**, 24k npm downloads, 9.7k stars. So:

- **The category's audience is in the hundreds of thousands,** not thousands: over 100k developers wanted to *see*
  their agents. Installs are not users, but the order of size is the signal.
- **Most of the reach came through a marketplace,** where developers already are, one click, no terminal. GitHub
  stars were the smaller channel. Orkline's install today is Homebrew or `curl` and Python: more friction, and no
  marketplace at all.
- **Install ≫ community** (126k against 155 in the Discord): a marketplace brings people who look once; the
  community is still built by hand.

**Q22 for the owner: a way in from a marketplace.** Claude Code has plugin marketplaces, the place this audience
already installs from. A small Orkline plugin there (the hooks of Q16, failing open, and one `/orkcraft` command
that opens the town or offers to install it) would be **an entry, not a second face**: the GUI stays the one face
(CLAUDE.md). An editor extension of the same kind later. *Default:* considered with Q21 (the first look at running
sessions), since both are the same way in; P1 after the testers, unless the launch's channels say sooner.

## 3. What to take from them

| from | what | where it goes | priority |
|---|---|---|---|
| Pixel Agents, AgentVille | **a free first look:** existing sessions shown with no change to how the person works (`npx`, an extension) | an open question for the owner, Q21 below | — |
| all | **work drawn as motion by what is done** (typing, reading, hammering) | already the rule ([town-readability.md](town-readability.md) §2.3) | P0 with the colour pass |
| Agent Village, AgentVille | **hooks fail open:** the AI tool works as usual when Orkline is not running | a rule for the hooks ([open-questions.md](open-questions.md) Q16) | P0 before the launch |
| AgentVille | Claude Code's limits read by wrapping its status line; Codex's from its session logs | a way to answer R5 | with R5 |
| Pixel Agents | a layout editor and outside asset packs | the community's buildings ([open-questions.md](open-questions.md) Q19); not before | Later |

**Not taken:** a building per kind of tool call (ours is a step of a flow); 3D; a VS Code extension as the main face
(the GUI is the one face).

## 4. The story against them

- **Never "your agents as pixel characters":** that is the category, and Pixel Agents owns it.
- **The difference in one line:** "They show your agents. Orkline runs the work: tasks go down roads between
  buildings, through a review gate, and the game is spending less per accepted result."
- **The question to prepare for the launch** ("how is this different from Pixel Agents?"): the line above, a GIF of a
  cart going from the board to the gate with its pull request, and Mission 1.
- **No word against them:** they are open source, and their users are this audience. Mentioned with respect;
  integration possible later (their office as a look, or Orkline's carts shown in their world).

## 5. Q21 for the owner: a first look at the sessions the person already runs?

Pixel Agents' reach comes from a zero-cost start: install, and the agents already working are there. Orkline asks
the person to run work through the town first. **An option:** Mission 1's first moment shows the person's live Claude
Code sessions as orks wandering the camp (the hooks of Q16 already see them); the quests then give them a board, a pool
and a gate.

- **For:** the first win in seconds and on real work; the bridge from "what I do today" to the town; it answers
  "how is it different" by showing it.
- **Against:** orks without carts or buildings blur the model of three things; the hooks are asked before the
  first quest instead of before quest 4; one more thing to keep working as Claude Code changes.

*Default until answered:* not in Mission 1; considered with the testers' first week, if the first win is measured
slower than 3 minutes ([first-mission.md](first-mission.md) §5).
