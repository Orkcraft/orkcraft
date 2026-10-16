# Spec 18 — darker, richer grass (variant B)

Branch `spec/18-darker-grass` · model **flash** · design: decisions §29, color-pass.md (quiet ground, loud signals)
**Builds:** agy · **Review:** light (docs/specs/README.md "Who builds")

## Why
The owner, 16 October: Camp's light grass catches the eye and distracts from the buildings and the signals. Of four
previews ([img/grass-variants.png](../design/img/grass-variants.png)) he chose **B: darker and richer**.

## The grade (exactly this, in this order, alpha kept as it is)
PIL: `ImageEnhance.Color(rgb).enhance(1.30)` → `ImageEnhance.Brightness(…).enhance(0.75)` →
`ImageEnhance.Contrast(…).enhance(0.90)`. A colour change only: the art rule (CLAUDE.md "Art") still holds — no
resize, no re-cut, no palette reduction, every pixel stays where it is.

## Do
Change only the files below, a new `tools/grass_grade.py`, `design-system/tokens.css` and the test named below.
Change nothing outside these files.
1. **`tools/grass_grade.py`**, run once: it reads each tile **from git at `223c414b`** (`git show 223c414b:<path>`), never
   from the working tree, so running it again gives the same files and never grades twice.
2. **Whole tiles, graded whole** (all in `design-system/sprites/v3/ground/`): `grass-1.png` … `grass-4.png`,
   `grass-tufts-1.png`, `grass-tufts-2.png`, `grass-flowers.png`, `tufts.png`, `flowers.png`.
3. **Mixed tiles, grass pixels only** (grass beside the path's earth): `rim-n.png`, `rim-s.png`, `rim-e.png`,
   `rim-w.png`, `corner-ne.png`, `corner-nw.png`, `inner-ne.png`. A pixel is grass when `g > r + 15` and
   `g > b + 15`; only those take the graded colour (the same grade computed on the whole tile, then copied where the
   mask is true). Earth pixels stay exactly as they are, so the path matches `earth*.png`.
4. **The tokens** in `design-system/tokens.css`, in the `:root, [data-theme="camp"]` block only:
   `--world-grass: #589224`, `--world-grass-light: #669b30`, `--world-grass-dark: #2c6835` (the same grade).
   The other blocks (Office and the rest) are untouched.

## Tests
Critical tests, plus `tests/test_design.py tests/test_gui_camp_browser.py`, and a new `tests/test_grass_grade.py`:
the script run twice gives identical bytes; an earth pixel of `rim-n.png` is unchanged from `223c414b`; a grass pixel
of `grass-1.png` is darker than at `223c414b`. Screenshots into `docs/design/img/grass/`: the camp at the default zoom
before (from `main`) and after, and one close-up of a path's edge after, so the review sees no seam between the rim
tiles and the earth.
