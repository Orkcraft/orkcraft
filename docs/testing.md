# Testing

## The tests (every pull request)

`pytest -q -n auto` runs ~1,300 tests in seconds, offline and free. No model runs in them: the orks'
tools are stand-ins (`tests/pool_fakes.py`) or what a real tool once printed (`tests/fixtures/`).
That shows how orkcraft reacts to an answer, never whether the tool still answers that way.

## The live bench (`tests/live/`, every night)

Orkcraft starts other programs (`claude`, `codex`, `pi`, …) and reads what they print
(`realm/harnesses.py`). A new release of one of them can change its flags or its output, and the
tests above stay green. The live bench runs the real tool on a real, cheap model and checks what
orkcraft gets back:

- **an answer**: text, its price, its tokens and its session (`h.result`), and a decision on the tool
  (`builders.ask`);
- **a reading agent** (`roads.run_agent`) reads the repository and can write nothing;
- **a worker** (`jobs.run_work`) works on a task branch the way the Barracks starts it: it edits and
  commits, a follow-up resumes its session, the check passes, the branch has a diff;
- **a failure says why**: a provider's refusal (a wrong key) comes back as one readable line, not
  as an empty answer.

It checks the shape of what comes back, never the model's wording.

```bash
npm install -g @earendil-works/pi-coding-agent
export GEMINI_API_KEY=…                               # Google AI Studio
pytest -m live --live                                 # skipped without --live, pi or the key
pytest -m live --live --refresh-fixtures              # … and rewrites tests/fixtures/pi_json_*.jsonl
```

| variable | default | |
|---|---|---|
| `ORKCRAFT_LIVE_MODEL` | `google/gemini-flash-lite-latest` | pi's `provider/id` |
| `ORKCRAFT_LIVE_BUDGET` | `0.25` | USD; once the run has spent it, the rest are skipped |

`.github/workflows/live.yml` runs it nightly and by hand (Actions → live → Run workflow) with the
`GEMINI_API_KEY` secret of the repository. It never runs on a pull request: it costs money, and its
red means a tool changed, not that the pull request broke something.

**What's on the bench.** pi on Gemini, because it takes a plain API key. Claude Code, Codex,
Antigravity and Cursor log in to a subscription, which a CI machine should not hold. Their output
is recorded in `tests/fixtures/` by hand for now; a live test of each, run on a machine that is
logged in, is the next step.
