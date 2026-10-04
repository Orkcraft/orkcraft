# Buildings section: how the screenshots were made

Every picture is the real app (`OrkcraftApp`, headless) on a sandbox made by the showcase's own
builder (`orkcraft.demo.build`), one sandbox per class, seeded with that class's demo data.

- `classes.py` builds a class sandbox: one orkspace with its eight buildings, a git repository,
  branches, a stand-in `gh` that lists fictional pull requests (the sandbox has no GitHub), and
  helpers for the Barracks, the Council, the ledger and the Watchtower's signals.
- `seed_<class>.py SANDBOX` makes the sandbox of a class.
- `shoot_<class>.py SANDBOX OUT` opens each building maximized in a 56×15 terminal, once in Camp
  and once in Office, from a fresh copy of the sandbox, and crops its window (56×12 cells).
  `shootlib.py` renders the crop as SVG and PNG (DejaVu Sans Mono 20 px at 4.5×, 16 px margin,
  padded to 2.3:1), hides scrollbars, keeps simulated orcs at work and freezes the clock so the
  two modes show the same times.
- `make_json.py ../buildings.json` writes the section's JSON from `selection.py` and `alts.py`.
- `textcheck.py OUT` flags personal data in the drawn text; `paircheck.py OUT` checks that Camp
  and Office of a building differ only in the window's frame row; `sheet.py OUT CLASS FILE` makes
  a contact sheet at 390 px.

```bash
for c in peon knight elf lich; do
  python seed_$c.py work/$c && python shoot_$c.py work/$c shots
done
python textcheck.py shots && python paircheck.py shots
python make_json.py ../buildings.json
```
