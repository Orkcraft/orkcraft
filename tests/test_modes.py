"""The town's one look: fire, rocks and gold in the terminal, and one word for each concept."""
from __future__ import annotations



from orkcraft.realm import modes

SIZE = (200, 56)
ASKING = "🧌 Peon 🔨 🔥"


def test_emoji_go_and_the_text_stays():
    assert modes.strip_emoji("🌾 Task fields") == "Task fields"
    assert modes.strip_emoji("[🪙 $1 / $5]") == "[$1 / $5]"
    assert modes.strip_emoji("✓ all reviewed · 02:15 → done") == "✓ all reviewed · 02:15 → done"
    assert modes.strip_emoji(" 👍 ") == "+1" and modes.strip_emoji(" 🗑 ") == "Delete"
    assert modes.strip_emoji("🗑️ Scroll dump") == "Scroll dump"
    assert modes.strip_emoji("0 results · 👍 3 👎 1") == "0 results · +3 −1"                    # an icon in a name just goes
    assert modes.plain("🌾 Fields") == "Fields" and modes.plain("🗼 Watchtower") == "External listeners"
