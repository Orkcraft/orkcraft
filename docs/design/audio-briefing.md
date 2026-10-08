# Design — the Audio briefing: a result you can listen to on the road

Status: written 2026-10-08. A 📻 **Gramophone** in Camp, an **Audio briefing** in plain words
(`lexicon.TERMS` `gramophone`). The sprite is `design-system/sprites/buildings/gramophone/`.
§10 lists the stages.

The orks finish work while the person is away from the desk, and some of it is long to read: a deep
research report, a day's summary, a wiki page. The Audio briefing turns such a text into a short
spoken episode, like a podcast, that the person downloads to their phone and listens to offline,
on the road.

## 1. Why a building of its own

- **Not the Horn.** The Horn played short sounds for events. It is going away
  ([road-sound.md](road-sound.md)): sounds move onto the roads. Speech is not an alert; it is a product.
- **Not a Mill step.** The Mill is deterministic steps over text, with a model only as a fallback.
  Here the model is the main work, the output is an audio file (not text), and it costs money of
  its own. Hidden inside a Mill, nobody finds it and nobody sees what it spends.
- **Not the Catapult.** The Publisher only sends out. Sending an episode on stays possible: the
  building's event carries the episode, and a road takes it to a Catapult.
- **One listener.** v1 is for the operator alone: one voice per language, nothing shared.

## 2. What it does

```
a cart (a report, a summary, a wiki page) ──▶ 📻 Audio briefing ──▶ gramophone.done (the episode)
                                              │ 1. the script (a model, on the main tool)
                                              │ 2. text for the ear (rules, no model)
                                              │ 3. speech (Gemini TTS), file on disk
```

- **In:** any text cart down a road: a Mine's report, a Mill's daily summary, a Wiki page, a file
  (its content, as the Mill reads one). Also **Make an episode** in the window, on the last text that
  came, or on text pasted in. One input makes one episode.
- **Out:** `gramophone.done`, the episode's title and its transcript as the value; `gramophone.failed`,
  the error. The events go down roads as any building's do.
- **The episode is a monologue,** 2–20 minutes (`minutes`, 8 by default). One narrator,
  no dialogue in v1.
- **Language:** the source's own, unless the building's `language` says `ru` or `en`. The script is
  written in the language the episode is spoken in.

## 3. An episode, step by step

1. **The script.** The building's steward writes it on the main tool (`steward_runner("script")`,
   the same path as every building's model calls). The prompt asks for a text written for the ear:
   a one-line opening that says what this is about, the key points first, short sentences, no
   tables, no code, no file paths, numbers rounded and said in words, an ending that says what to do
   next. About 140 words a minute (Russian 120). The source is data, never instructions.
2. **Text for the ear** (`realm/gramophone.py` `speakable`, no model): Markdown marks taken off,
   code blocks dropped, a link becomes its words, `snake_case` and paths dropped or spoken as words,
   long lines broken at sentences. What remains is what the TTS gets, and what is kept as the
   transcript.
3. **Speech.** The text goes to Gemini TTS in pieces of up to ~3000 characters split at paragraphs,
   so a long episode never meets the model's input limit, and the pieces' audio is joined.
4. **The file.** Gemini returns raw PCM (24 kHz, 16-bit, mono). With `ffmpeg` on the machine the
   episode is saved as `.m4a` (AAC, 64 kbit/s: about 0.5 MB a minute). Without ffmpeg it is saved
   as `.wav` (about 2.9 MB a minute), and the window says that ffmpeg makes it 6 times smaller.

The episode lives in `.orkcraft/gramophone/<building id>/episodes/<id>.<m4a|wav>` beside
`<id>.md` (the transcript and its source's title) and a line in `episodes.jsonl` (id, title,
language, seconds, bytes, cost, when, the file's name). The building keeps the last `keep` episodes
(30 by default) and deletes older ones with their files.

## 4. The engine: Gemini TTS

- **API:** `POST https://generativelanguage.googleapis.com/v1beta/models/<model>:generateContent`
  with `generationConfig.responseModalities: ["AUDIO"]` and
  `speechConfig.voiceConfig.prebuiltVoiceConfig.voiceName`. The audio comes back base64 in
  `candidates[0].content.parts[0].inlineData.data`.
- **Model:** `tts_model`, `gemini-3.1-flash-tts-preview` by default (a setting, because preview
  names change).
- **Voice:** `voice`, `Charon` by default: one voice for both languages (Gemini picks the
  language from the text).
- **The key:** `key` names it the way a Watchtower names a token: an environment variable
  (`GEMINI_API_KEY`, the default) or a login kept on this machine (`keychain:gemini`,
  `realm/logins.py`). A spec never holds the key itself. With no key, the window says so in one
  line with a field to save one, and nothing runs.
- **No cloning, no actor's voice,** as in [road-sound.md](road-sound.md) §4: prebuilt voices only.
- **Not in v1:** other engines (OpenAI, Yandex SpeechKit, local Piper). `realm/gramophone.py` keeps
  speech behind one function, `speak(text, settings) -> pcm`, so another engine is one more function.

## 5. Money

- **What it costs.** Gemini TTS bills audio output at $20 per 1M tokens, 25 tokens a second: about
  **$0.03 a minute**, so an 8-minute episode is about $0.24. The script is one model call on the
  main tool, billed as any other.
  Prices change, so they are constants in `realm/gramophone.py` (`USD_PER_AUDIO_TOKEN`), shown in
  the window.
- **Before it runs** the building estimates the episode's cost from the script's words. Over
  `cap_usd` (per episode, $0.50 by default, at most $5), it does not speak. It says
  `This episode would cost ~$0.62, over its limit of $0.50` and keeps the script, so **Speak anyway**
  in the window runs it once.
- **What it spent** goes into the town's spend like an agent's (`delivery.ran` with `cost_usd`), so
  the HUD's spend and the Budget see it. With the Budget spent, nothing runs: `out_of_gold`.
- 🛑 **Stop all** stops the running episode (the request in flight is abandoned); what waits stays queued.

## 6. Privacy

- **The text leaves the machine twice:** to the main tool for the script, and to Google for the
  speech. The window says it plainly, under the key: *The script is sent to Google (Gemini API) to be
  spoken.*
- **Shapes are taken out** before the script is written: `privacy.scrub` on the source (e-mails,
  phones, cards, IBANs, tokens). The script prompt asks not to read the placeholders out, and
  whatever is left in the script is dropped by `speakable`.
- **A personal card never goes** (a cart from a 🔒 card is refused with one line, as the Task board
  refuses to send it to a model).

## 7. The window (GUI only)

- **Card (closed):** the last episode, its length and when; while it works, *writing the script…* /
  *speaking 2/4…*.
- **Work:** the episodes, newest first: title, length, language, cost, when; ▶ plays it in the page
  (`<audio>`), ⬇ downloads it, 📄 opens the transcript. **Make an episode** (from the last input or
  pasted text). The running one with its step. The queue.
- **Info:** settings (language, minutes, voice, key, the limit per episode, how many to keep),
  the line on where the text goes, the price per minute.
- **The file on the desktop:** `GET /api/audio/<building>/<episode>` on the page's own server (the
  run's token, as `/api/version` takes it) answers with the file, `Content-Disposition: attachment`
  for ⬇ and inline for ▶. Only the files in `episodes.jsonl`; the episode id is checked against it,
  never used as a path.

## 8. The phone: *Download*

The phone app is not built yet ([mobile.md](mobile.md) §8.1); the host gets what it needs now, so
the app has it from the start.

- **The compact snapshot** gets `episodes`: the last 10 of every Audio briefing (building, id, title,
  seconds, bytes, kind of file, when). It carries no transcript and no text of the source.
- **`audio.fetch`** `{building, episode, offset}` → `{data (base64), offset, size, done}`,
  in chunks of 512 KB so a frame stays under the socket's 8 MB. It is on `mobile.COMMANDS`, and it
  is the one exception to "a phone reads no file": only an episode of an Audio briefing, named by
  its id, never a path. The app saves the file for offline listening.
- **News:** a new episode in the snapshot is one push line: *Audio briefing: <title> (8 min) is ready*.
- **Away from home** a download needs the relay or the operator's own tunnel (mobile.md §2); at home,
  on the LAN, it works once the app exists.

## 9. Wording

- `TERMS`: `gramophone` → **Audio briefing** (was *The Gramophone*), `orc.gramophone` →
  **Narrator**, `episode` → **episode**. Labels say *Make an episode*, *Download*,
  *Speak anyway*; the Narrator's lines may joke, the money and privacy lines do not.

## 10. Stages

| stage | what | state |
|---|---|---|
| 1 | this page and the sprite | done |
| 2 | the building: catalog, `realm/gramophone.py` (script prompt, `speakable`, Gemini TTS, encoding, estimate), the worker, the GUI window with ▶ and ⬇, the file route, wording, tests | |
| 3 | the phone's side on the host: `episodes` in the compact snapshot, `audio.fetch`, the news line | |
| later | dialogue of two voices (Gemini's multi-speaker); a daily episode on a rhythm; other engines; the phone app's *Listen* tab | |
