# The design system

How orkcraft looks, written down as data so that people, the terminal face, a future GUI and
the orks that rebuild buildings all follow the same rules. Background: [docs/design/gui-migration.md](design/gui-migration.md).

| What | Where |
|---|---|
| Tokens: font roles, colour roles, space | `orkcraft/design/tokens.json` (read by `design/tokens.py`) |
| A building's UI document, its schema | `orkcraft/schemas/building-ui.v1.json` |
| What each type's window has (its contract) | `orkcraft/design/buildings/<type>.json` |
| Checking a document, the rules a model gets | `orkcraft/design/ui.py` (`validate`, `RULES`) |
| How the terminal draws a document | `orkcraft/tui/ui_apply.py` |

## 1. Tokens: roles, not values

A document never says "18 px Cinzel in #ff8c1a". It says `"font": "title", "tone": "fire"`, and each
face looks the role up.

**Font roles**

| role | for | GUI (camp / office) | TUI |
|---|---|---|---|
| `title` | a building's name, a dialog's heading | display face, 18, bold | bold |
| `heading` | a pane's or a section's heading | display face, 15, semibold | bold |
| `body` | running text: notes, Markdown | text face, 14 | as is |
| `mono` | code, diffs, paths, terminals, the editor | mono face, 13 | as is |
| `status` | the short live lines | text face, 12 | the view's muted colour |
| `label` | a field's or a column's name, a key | text face, 12, semibold | bold, dim |
| `number` | counters, money, tokens, percentages | mono face, 14, semibold | bold |

The faces: Camp uses Cinzel for display and Alegreya Sans for text. Office uses Inter for both.
Both themes use JetBrains Mono for code. All of these fonts are under the OFL, with system fallbacks.

**Colour roles** (`tone`): `text`, `muted`, `accent`, `ok`, `wait`, `fire`, `error`; and the frame
and ground roles `canvas`, `surface`, `frame`, `frame_focus`, `road`, `road_selected`; and one per
harness (`harness.claude`, `harness.agy`, `harness.codex`, `harness.pipeline`). Camp and Office give
each role their own value. **`fire` means one thing only: something waits for the person.**

**Space**: steps 0–6, which are pixels in a GUI (0, 4, 8, 12, 16, 24, 32) and cells in the terminal.

## 2. A building's UI document

Every building has one. A building with no document of its own (nobody changed it) wears its type's
default. The document is kept in the building's entry of the Town Scroll (`ui`), so it is part of
every checkpoint, and `Z` takes a change back.

```json
{
  "version": 1, "type": "scrolls", "split": "column",
  "panes": [
    {"id": "head", "component": "status", "size": "auto", "font": "status"},
    {"split": "row", "size": 1, "panes": [
      {"id": "tree", "component": "tree", "size": 2, "font": "body"},
      {"id": "page", "component": "markdown", "size": 3, "font": "body"}
    ]}
  ],
  "note": "the page reads wider than the tree"
}
```

- **A pane** has an `id` from its type's contract and a `component`. It may also set `size`
  (`auto`, or 1–12 as a share of the room left), `font`, `tone`, `title` and `hidden`.
- **A group** has a `split` (`column`: one under another; `row`: side by side), panes, and
  optionally a `size`. Groups nest at most two deep.
- **The contract** of a type lists its panes, the components each may wear, and which panes are
  `required` (always there, never hidden) or `dynamic` (they show and hide themselves, like the
  Lake's editor). A type with no contract file is one pane, `main`: its own view.
- **Components** form a closed list: `status`, `text`, `markdown`, `diff`, `editor`, `list`,
  `table`, `tree`, `board`, `counter`, `chart`, `log`, `form`, `terminal`, `view`.

Contracts so far: 🌊 Lake (`head`, `view`, `editor`), 🌾 Task Fields (`board`), 🗑️ Scroll Dump
(`head`, `tree`, `page`). Every other type is one `main` pane for now. A type gets a contract when
its view is split into named panes (`TypedView.UI_PANES`).

**How the terminal draws it**: it applies sizes, the order among panes that share a parent, titles
on the frame, `hidden`, a font role as a text style and a tone as its colour. The terminal keeps a
view's own nesting, so a group the document moves elsewhere stays where the view has it. A GUI
draws the groups exactly as written.

## 3. Who changes a building's window

- **You, through its steward**: select the building, press **`D` 🎨**, and say what should change
  ("the tree narrower, the page larger"). The steward rewrites the document in one model call.
  It is checked against the contract, and a wrong answer goes back to the model with the problems.
  You see the new layout in one line. `Enter` keeps it, as a checkpoint `ui(<id>)`, and `Z` takes it
  back. Typing `default` puts the type's own layout back without a model call.
- **Not at night**: a new layout always waits for your `Enter`. The orks' own changes in quiet
  hours never touch a window.

## 4. The rules (what a model is given, word for word in `design/ui.py` `RULES`)

1. Change only what was asked, and leave every other pane as it is.
2. Use only the contract's panes, and for each only the components it lists. A required pane stays
   and is never hidden. A dynamic pane shows and hides by itself.
3. Name roles, never values. No colours, font names, pixel sizes or code.
4. Pick fonts by meaning: `title` for a name, `heading` for a pane, `body` for text, `mono` for
   code, paths and diffs, `status` for live lines, `label` for field names, `number` for counters
   and money.
5. Tones mean something: `ok`, `wait` and `error` as they say, and `fire` only for what waits for
   the person. Most panes have no tone.
6. Sizes: `auto` for a pane as tall as its content. Otherwise a share, and the pane people read
   most gets the largest one.
7. Put panes side by side only where both halves stay readable, such as a list beside its detail.
8. The town stays simple: a layout never adds roads, ports or settings to the map. A building's
   settings live in its window.
9. Give a pane a title only when its content does not say what it is.
10. Write the `note`: one sentence on what changed and why.

## 5. The town stays simple

These hold for any face, Office and Camp alike:

- There is one kind of edge, the road. A building has no ports or parameters on the canvas.
- On the map a building shows its name and up to three status lines. Its settings and its work
  live inside its window.
- Where a building stands is the person's choice, never an automatic layout.
