# Service glyphs

One glyph per outside service the town talks to — a Watchtower source, a connector, an MCP server:
GitHub, GitLab, Gmail, Discord, Jira, Confluence, Figma. They tell *which service* a row, a tile or a
chip is about; they are never decoration and never a button by themselves (a label stands beside
each one).

## Where they come from

- **Simple Icons** (https://simpleicons.org), CC0-1.0: one path, `viewBox="0 0 24 24"`, no colour.
  Take them from the npm package, not a CDN: `npm pack simple-icons`, then
  `package/icons/<slug>.svg`. These are from simple-icons 16.34.0.
- The file is named by the service's id in orkcraft (`realm/quickadd.py` `SERVICES`, a feed's kind,
  an MCP server's name): `jira.svg`, `figma.svg`. One file per service, no variants.
- **Never draw a logo ourselves**, and never take one from the brand's own site. A brand that is not
  in Simple Icons — or was taken out at its owner's request, as Slack's was — gets **no glyph**: its
  place shows a text mark instead (Slack: `#`). Note such a service in the list below.
- Before adding a file, check it is only a path: no `<style>`, `<script>`, `<foreignObject>`, `href`,
  `fill`, embedded image or animation; under 2 KB. Keep the `<title>`.

## How they are drawn

- **One colour, the town's, never the brand's.** The SVG is a CSS mask; the colour is a role token —
  `--ink-gold` in Camp (the frame's gold), the same in Office. A brand colour would shout over the
  muted Camp palette and break Office's calm; one colour keeps every service equal.
- **In a well.** The glyph sits centred in a small square that looks like the other wells of the
  design system: `--panel-inset` with `--bevel-sunken` (Office: a 1px `--frame` hairline instead),
  `--ok-radius` corners. The glyph fills 62% of the square.
- **Two sizes**: 22px in tiles, chips and lists; 34px at the head of a step or a source row.
- **Not pixel art.** Glyphs are vector marks of other companies' products; the town's own things
  (buildings, orks, resources) stay sprites (design-system/Sprites).
- **Accessible**: the glyph is `aria-hidden`; the service's name is always written next to it.

The markup and CSS (as `js/buildings/watchtower.css` uses them):

```html
<span class="gui-svc gui-svc--jira" aria-hidden="true"></span>       <!-- Slack: <span …>#</span> -->
```

```css
.gui-svc { display: inline-grid; place-items: center; width: 22px; height: 22px; background: var(--panel-inset);
  box-shadow: var(--bevel-sunken); color: var(--ink-gold); font: 700 13px/1 var(--ok-font); border-radius: var(--ok-radius); }
.gui-svc.is-big { width: 34px; height: 34px; font-size: 18px; }
.gui-svc::before { content: ""; width: 62%; height: 62%; background: var(--ink-gold);
  -webkit-mask: var(--svc) center / contain no-repeat; mask: var(--svc) center / contain no-repeat; }
.gui-svc--jira { --svc: url("…/icons/services/jira.svg"); }      /* one line per glyph */
[data-theme="office"] .gui-svc { box-shadow: inset 0 0 0 1px var(--frame); }
```

## The glyphs

| Service | File | Note |
|---|---|---|
| GitHub | `github.svg` | |
| GitLab | `gitlab.svg` | |
| Gmail | `gmail.svg` | |
| Discord | `discord.svg` | |
| Jira | `jira.svg` | |
| Confluence | `confluence.svg` | |
| Figma | `figma.svg` | |
| Slack | — | not in Simple Icons (removed at Slack's request): the text mark `#` |

## Adding one

1. `npm pack simple-icons`, copy `package/icons/<slug>.svg` here as `<service id>.svg`.
2. Check it as above (a path only, under 2 KB).
3. Add its `.gui-svc--<id>` line to the stylesheet that draws it, and its row to the table here.
4. Not in Simple Icons: no file — a text mark, and a row saying so.
