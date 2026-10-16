# Spec 19 — Camp's camera: no far zoom-out; the wheel scrolls down the lines

Branch `spec/19-camp-camera` · model **flash** · design: decisions §30
**Builds:** agy · **Review:** light (docs/specs/README.md "Who builds")

## Why
The owner, 16 October: pulled far back, the buildings stop reading and the empty wilderness round the camp (with its
randomly scattered trees) fills the screen. The default view, the whole railway across the screen, is the right one;
since new lines are added at the bottom, the person scrolls **down**, not out.

## Do
Change only `orkcraft/gui/static/js/zoom.js`, `orkcraft/gui/static/js/camp/town.js` and
`tests/test_gui_camp_browser.py`. Change nothing outside these files. Office is unchanged in every point.
1. **No zoom-out past the default in Camp:** the farthest level in Camp is `b` (today's default). `zoomBy`, ⌘−, a
   pinch, and `M` (the map) stop there; a stored `a` opens Camp at `b`. Closer levels (`bc`, `c`) stay.
2. **The wheel scrolls:** in Camp a plain wheel (and a trackpad's two-finger move) moves the view up and down
   (`pan.y`); Ctrl/⌘ + wheel and a pinch zoom, as today's wheel does.
3. **The view stays on the camp:** the pan is held so that, at `b`, the camp's width stays as it is (no sideways
   drift into the wilderness) and vertically it runs from the wall at the top to the last line plus one row of grass
   below; at `bc` and `c` the pan may move sideways, but never past the camp's own edges plus one tile. Opening a
   building (its focus) works as today.

## Tests
Critical tests, plus `tests/test_gui_camp_browser.py`: in Camp ⌘− and `M` at `b` leave the level at `b`; a stored
`a` opens at `b`; a plain wheel changes the vertical offset and not the level; Ctrl + wheel changes the level; the
view cannot be dragged past the last line plus a row, nor sideways at `b`; Office still reaches its map `a`.
