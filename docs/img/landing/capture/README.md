# Landing-page previews

How `../prev-*.png` were made: the real app runs headless with demo data. Each shot cuts one panel out of the
app's own render and draws it as an SVG with no window chrome (DejaVu Sans Mono 20 px, 4.5× in Chromium,
16 px margin).

```bash
orkcraft --demo DEMO --demo-reset                      # main set: War Map, garrison, Command Card
python -c "from pathlib import Path; from orkcraft import demo; demo.build(Path('DASH'), reset=True, set_name='dashboard')"
python seed_dash.py DASH                               # token ledger + a code-review Orc Council
python shoot_main.py DEMO OUT warmap                   # run each main-set shot on a fresh copy of DEMO
python shoot_main.py DEMO OUT overseer                 # (it adds three handlers to the Scrying Spire)
python shoot_main.py DEMO OUT command
python shoot_dash.py DASH OUT crag council
```
