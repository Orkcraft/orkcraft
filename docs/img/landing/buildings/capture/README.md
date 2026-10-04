# Buildings section: how the pictures were made

Every picture is the real app (`OrkcraftApp`, headless) on a sandbox made by the showcase's own
builder (`orkcraft.demo.build`), one sandbox per class, seeded with that class's demo data. Each
picture is one building as its hut on the town map, cropped to the hut: its name, its roof, its
body with the live status lines and its buttons. Camp shows the hut's ASCII silhouette on the ice
biome with the orc at the door; Office shows the same hut as a grey frame with words for icons.

- `classes.py` builds a class sandbox: one orkspace with the class's eight buildings, a git
  repository, branches, a stand-in `gh` that lists fictional pull requests (the sandbox has no
  GitHub), and helpers for the Barracks, the Council, the ledger and the Watchtower's signals.
- `seed_<class>.py SANDBOX` makes a class's sandbox.
- `hut_<class>.py SANDBOX OUT` shoots each building in Camp and in Office from a fresh copy of the
  sandbox (`hutlib.py`): the building in the middle of the map, the others in the corners, the
  crop exactly its hut, rendered at 8× (16 px margin). `shootlib.py` freezes the clock so both
  modes show the same times and keeps the simulated orcs at work; `shotlib.py` turns the
  terminal cells into SVG and PNG (DejaVu Sans Mono).
- `make_json.py ../buildings.json` writes the section's JSON from `selection.py` and `hut_alts.py`.
- `textcheck.py OUT` flags personal data in the drawn text; `hsheet.py OUT CLASS FILE` makes a
  contact sheet.

```bash
for c in peon knight elf lich; do
  python seed_$c.py work/$c && python hut_$c.py work/$c shots
done
python textcheck.py shots
python make_json.py ../buildings.json
```
