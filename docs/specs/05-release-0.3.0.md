# Spec 05 — release 0.3.0 "Orkline"

Branch `spec/05-release-0.3.0` · model **flash-low** · design: CLAUDE.md "Releases", docs/updates.md
**Builds:** agy · **Review:** light (docs/specs/README.md "Who builds")

Run only when the PM session says the release is ready (decisions §22: Thursday 22 October).

## Do
1. `orkcraft/__init__.py`: `__version__ = "0.3.0"`.
2. `updates.json`: a new entry **at the top** of `releases`: `version` "0.3.0", `date` (the day), `critical`
   false, and `notes` in plain words, under 600 characters, covering: the new name Orkline; Camp redrawn (the line and
   its stations, the depot, steel track, the wilderness, the new interface with wooden frames and parchment); Mission
   1 on the stations; the phone app reachable all day; the Workchief (renamed). The PM session will review the
   wording.
3. Nothing else.

## Tests
Critical tests (`tests/test_updates.py` checks the feed).

## Prompt
Use the prompt in docs/specs/README.md with `<NN-name>` = `05-release-0.3.0`.
