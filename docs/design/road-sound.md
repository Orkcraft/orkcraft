# Design — a road says what it carries, and how it sounds

Status: §2 built (GUI). §1 and §3 are being built on their own branch; this page is what they follow.

A sound answers a cart, and a cart travels on a road, so the road is where a person sets the sound. The
Horn, a building that held a table of `event: sound` lines for the whole town, goes away. Several roads
from one building into the same other one are one road, and its card lists every event it carries.

## 1. Why

- **Where you look.** "When mail comes in here, chime" is said on the road the mail comes down. With the
  Horn, a person had to know about one more building and its `building/event: sound` lines.
- **One building fewer.** The Horn did nothing but sound. A calm town has no building just for settings
  (docs/design/calm-town.md).
- **A sound tells what happened.** Done, failed and "needs you" sound different, even on the same road.

## 2. One road from one building into another (built)

- **Same direction, one road.** The roads from A into B are drawn as one road with every label
  (`js/town.js` `together`). The first road's path is planned, and the others' carts run on it.
- **A road the other way stays its own road.** A → B and B → A make a loop between the two, and the town
  shows it as two roads. The core refuses such a loop (`scroll_roads.subscribe`); only a return road
  (`{"returns": true}`, docs/design/fields-board.md §5a) may come back, and it is drawn as its own dashed road.
- **The card lists them all.** A click picks the whole road; the card (`js/build.js` `RoadBar`) says
  `A → B · 2 events` and has one row per event: what it carries, its handler, **Handler** and **Remove**.
  *Add an event* lays another road between the same two buildings (the road-in-words dialog).
  A road picked from the steward's roster opens the same card.
- **The data stays as it was.** Each event is still its own `Road` in the Town Scroll, with its own filter,
  handler or rule. Checks for duplicates, loops and limits stay per event, and scrolls written before load
  as they did. Only what a person sees is merged.

## 3. A sound on each event of a road

- **On the row, not the road.** The row of an event in the road's card gets a 🔊 picker: a built-in sound,
  a voice line (§4), an audio file of the person's own, or nothing, with ▶ to hear it. *All events* sets
  one sound for every row.
- **Local, not in the scroll.** The Town Scroll is the project file and goes to git and to the team. One
  person's siren must not sound for everyone, so a sound is kept in this machine's settings, by the road's
  town-wide key (`scroll.road_key`). The scroll keeps only the roads.
- **One cart, one sound.** An event that goes down three roads plays one sound, not three: within a short
  window, one sound per cart (its `ref`), and the most urgent wins (needs you > failed > done > the rest).
- **Quiet by default.** A new road makes no sound. The picker offers a sound right away for the events
  that ask for a person (`loot.needs_you`, `*.failed`, `signpost.unmatched`, `workshop.alert`).
- **What the Horn held moves to Settings → Sound:** mute, volume, quiet hours (`22:00-08:00`), the voice
  pack. Quiet hours stay: they keep the town calm at night.
- **The Horn goes.** A scroll with a Horn still loads: its lines move onto the roads they name where they
  can (`building/event`, `event`), `*` and `default` become the sound of Settings, and the Horn is
  demolished with one line saying where its sounds went.
- **Wording.** "Sound" gets its word in `realm/lexicon.py` `TERMS`, and its old Camp spelling "Horn" goes
  into `was`.

## 4. The voice pack

An ork answers an event in a few words, as a unit in a strategy game answers an order. The lines are
ours: we take the genre, never a game's lines or voices.

- **Never:** a recording from a game, even pitched or cut; a voice cloned from an actor or made to sound
  like one; a game's catch-phrases or close rewrites of them; a game's invented language; a game's name in
  the pack's name.
- **Free to use:** our own lines in the same genre, a gruff voice of our own, several takes per event
  picked at random (never the same one twice in a row), and an ork that grows cross when poked too often.
- **On disk:** a folder per kind of event, 3–5 takes in each; a road's sound may name a folder, and one
  take of it plays.

| Kind | Events | Lines |
|---|---|---|
| Work taken | `tasks.created`, `pool.assigned`, `tasks.sent` | "Fine. Ork go." · "More work? Grr." · "On it, boss." |
| Done | `pool.done`, `workshop.done`, `mill.done`, `team.artifact_ready` | "Built it. Mostly." · "Finished! Where's grub?" · "Smashed it good." |
| Failed | `workshop.failed`, `pool.failed`, `mill.failed` | "It broke. Not me." · "Bah! Thing fight back." · "Ork tried. Ork sad." |
| Needs you | `loot.needs_you`, `signpost.unmatched` | "Warchief! Need your eyes." · "Where this go?" · "Ork stuck. Help?" |
| Alarm | `workshop.alert`, `catapult.failed` | "Trouble at the walls!" · "Loud thing broke!" |
| Yes / again | `team.approved` / `team.rework`, `loot.rework` | "Warchief say yes!" · "Again?! Fine…" |
| Word came | `mail.received`, `watch.webhook`, `watch.github` | "Scroll come!" · "Raven bring word." |
| Git | `git.pr_opened`, `pr.merged`, `pr.closed` | "New road dug." · "Road is open!" · "Road gone. Oh well." |
| Sent on | `signpost.routed` | "That way!" · "Off you go." |
| Time | `watch.cron` | "Drum say: time." |
| Poked | clicked again and again | "Poke me again, I bite." · "Ork busy being ork." |

## 5. Making the sounds

Generate a raw take, then give it the ork's voice with the same chain for every take, so the pack sounds
like one ork.

| Tool | For | License (check before shipping) |
|---|---|---|
| Gemini TTS (`gemini-2.5-pro-preview-tts`, `…-flash-preview-tts`) | voice lines: the voice is a prebuilt one (e.g. `Algenib`, gravelly; `Charon`; `Orus`), the delivery is said in words | the Gemini API terms; no cloning, so no one's voice |
| Kokoro (82M) | voice lines, local, many takes | Apache-2.0 |
| Bark | grunts, laughs, growls between words (`[laughs]`, `…`) | MIT; takes vary, make several |
| Piper | fast local voices | MIT engine; each voice has its own license |
| Stable Audio Open 1.0 | short effects: drums, horns, carts, coins | Stability AI Community License (free under its revenue limit) |
| sfxr / jsfxr | blips, dings, chimes | output is yours |
| sox / ffmpeg / rubberband | the ork's voice: pitch, formants, grit, room | GPL/LGPL tools; what they make is yours |

Not to use: AudioGen / MusicGen weights (CC-BY-NC, non-commercial), Coqui XTTS (CPML, non-commercial),
any voice-conversion model trained on a game's voices.

**The ork's voice** (one chain for every take; formants stay put so words keep clear):

```sh
rubberband -p -4 --formant raw.wav low.wav          # four semitones down, formants kept
sox low.wav ork.wav overdrive 6 12 bass +4 treble -2 reverb 18 50 30 norm -1 silence 1 0.05 -50d reverse silence 1 0.05 -50d reverse
ffmpeg -i ork.wav -c:a libvorbis -q:a 5 ork.ogg     # small files for the pack
```

### Voice prompts (Gemini TTS; with Kokoro and Bark, the line alone)

Every prompt starts with the same voice so the pack is one ork:
*"A low, gravelly, slightly hoarse voice of a big, good-natured ork laborer. Short, blunt words, broken
grammar on purpose, a small grunt before or after. Not a monster, not scary: tired, loyal, a bit funny."*

1. **Work taken** — "Grudgingly, with a sigh, then agreeing: *Fine. Ork go.*"
2. **Work taken** — "Grumbling under the breath, annoyed but obedient: *More work? Grr.*"
3. **Work taken** — "Quick and keen, already walking off: *On it, boss.*"
4. **Done** — "Proud, then a little unsure, a short pause before the last word: *Built it. … Mostly.*"
5. **Done** — "Cheerful, loud, hungry: *Finished! Where's grub?*"
6. **Done** — "Smug, slow, satisfied chuckle at the end: *Smashed it good.*"
7. **Failed** — "Quickly, defensive, like a kid caught out: *It broke. Not me.*"
8. **Failed** — "Angry snort, then muttering: *Bah! Thing fight back.*"
9. **Failed** — "Sad and slow, a sigh: *Ork tried. Ork sad.*"
10. **Needs you** — "Calling across a yard, urgent but not panicked: *Warchief! Need your eyes.*"
11. **Needs you** — "Puzzled, scratching the head, rising at the end: *Where this go?*"
12. **Needs you** — "Embarrassed, quieter: *Ork stuck. Help?*"
13. **Alarm** — "Shouted, out of breath, from far away: *Trouble at the walls!*"
14. **Yes / again** — "Delighted, a short laugh: *Warchief say yes!*" / "Outraged, then giving in: *Again?! … Fine.*"
15. **Word came** — "Excited, announcing: *Scroll come!*" / "Matter-of-fact: *Raven bring word.*"
16. **Git** — "Pleased, like opening a gate: *Road is open!*" / "Shrugging: *Road gone. Oh well.*"
17. **Poked** — "Fed up, through the teeth, then a small growl: *Poke me again, I bite.*"

### Effect prompts (Stable Audio Open; 1–3 s, then the same `norm -1` and fade)

18. "Two heavy hits on a big wooden war drum, outdoors, short decay, no music, 2 seconds."
19. "A short low horn call made of an animal horn, three rising notes, outdoors, slight echo, 3 seconds."
20. "A wooden cart with iron wheels rolling briefly over cobblestones and stopping, 2 seconds."
21. "A small pile of gold coins dropped onto a wooden table, bright clinks, 1 second."
22. "A single soft bell rung once in a quiet stone hall, gentle, 2 seconds."

Every take is heard by a person before it goes into the pack; one that sounds like a game's line or
voice is thrown out.
