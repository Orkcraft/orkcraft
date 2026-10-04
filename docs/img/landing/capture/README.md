# Landing-page previews

How `../prev-*.png` were made: the real app runs headless with demo data. Each shot cuts one panel out of the
app's own render and draws it as an SVG with no window chrome (DejaVu Sans Mono 20 px, 4.5× in Chromium,
16 px margin).

```bash
orkcraft --demo DEMO --demo-reset                      # main set: town, HUD, garrison, Command Card
python -c "from pathlib import Path; from orkcraft import demo; demo.build(Path('DASH'), reset=True, set_name='dashboard')"
python seed_dash.py DASH                               # a code-review Orc Council
python seed_town.py TOWN 0.05 0.33 0.2 0.55            # TOWN = a copy of DEMO: Feat-OAuth huts in a triangle
python shoot_town.py TOWN OUT 150 44 3 6 6 66 22       # prev-war-map.png: three huts, roads, carts
python shoot_hud.py TOWN OUT                           # prev-token-budget.png: the 🪙 / 🪵 / 🥩 counters
python shoot_main.py DEMO OUT overseer                 # (it adds three handlers to the Scrying Spire)
python shoot_main.py DEMO OUT command
python shoot_dash.py DASH OUT council
```
