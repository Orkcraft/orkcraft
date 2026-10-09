"""Every biome's ground is dark (docs/design/yards.md §3e): darker than a card, so a card reads as a plane on it,
and dark enough that a card's words read on the ground itself — the cards' background may be left out in Camp
(Card background: Yard or Ground). A light biome would need a card's panel under its words; none may be added."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ICONS = ROOT / "orkcraft" / "gui" / "static" / "js" / "icons.js"
TOKENS = ROOT / "design-system" / "tokens.css"


def _luminance(hex_: str) -> float:
    rgb = [int(hex_[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def _contrast(a: str, b: str) -> float:
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _grounds() -> dict[str, str]:
    text = ICONS.read_text(encoding="utf-8")
    block = text[text.index("export const BIOMES"):text.index("export const BIOME_ORDER")]
    return dict(re.findall(r'(\w+): \{ ground: "(#[0-9a-fA-F]{6})"', block))


def _camp(token: str) -> str:
    text = TOKENS.read_text(encoding="utf-8")
    camp = text[text.index(':root, [data-theme="camp"]'):]
    return re.search(rf"--{token}: (#[0-9a-fA-F]{{6}});", camp).group(1)


def test_every_ground_is_darker_than_a_card_and_its_words_read_on_it():
    grounds = _grounds()
    assert len(grounds) >= 7, grounds                      # dirt, forest, ice, dust, void, lava, meadow
    panel, ink, muted = _camp("panel"), _camp("ink"), _camp("ink-muted")
    for name, ground in grounds.items():
        assert _luminance(ground) < _luminance(panel), f"{name}: its ground is lighter than a card"
        assert _contrast(muted, ground) >= 4.5, f"{name}: muted words would not read on its ground"
        assert _contrast(ink, ground) >= 7, f"{name}: words would not read on its ground"
