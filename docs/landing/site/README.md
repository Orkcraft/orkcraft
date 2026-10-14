# The landing page (draft, D4)

One static page for orkline.dev, in the order of [launch-prep.md](../../design/launch-prep.md) §2b. No framework, no
build step, nothing loaded from another host: `index.html`, `style.css`, the design system's fonts (`fonts/`, SIL OFL
1.1, licences beside them) and its Camp and Office colour tokens, copied into `style.css`.

Look at it locally (the fonts need http, not `file://`):

```bash
python3 -m http.server -d docs/landing/site 8000
```

`screenshot-desktop.png` (1440 px) and `screenshot-phone-390.png` (390 px) are renders of this draft.

## What the owner fills in before deploying

- **The community link:** `index.html`, `id="community"` (now "opens soon", not clickable).
- **The visual:** the hero is the concept frame (`img/camp-concept-*`, marked "Concept art"); swap in the GIF or video
  with `img/camp-concept-1280.jpg` as its poster once it is filmed.
- **`og:url` and an absolute `og:image`** on orkline.dev.
- **The install line:** today's real one, `curl -fsSL https://orkcraft.dev/install.sh | sh`. If orkline.dev serves
  the installer later, change it here and in the README together.
- **The example score line** ("12 launched this week · 30 % less wood each") is an illustration; the score is P1
  ([the-score.md](../../design/the-score.md)).
