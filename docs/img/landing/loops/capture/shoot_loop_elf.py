import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from looplib import run

EMITS = [
    ("pit", "pit.text", "Hero section, 3 variants: warmer CTA", "brief"),
    ("grunts", "pool.done", "Hero B — Artisan · hero-b.md", "hero-b"),
    ("review", "team.artifact_ready", "agreed in round 2: hero-b, focus order fixed", "verdict"),
    ("vault", "generator.rejected", "hero-a.md: CTA too loud", "hero-a"),
    ("vault", "generator.accepted", "design/tokens.json", "tokens.json"),
]
async def prep(app):
    import asyncio
    from orkcraft.screens.typed.lake_view import LakeView
    for v in app.query(LakeView):
        v.show_value("markdown", "# Hero B\n[ Start free ]\nwarmer CTA, focus order fixed", "hero-b.md")
    await asyncio.sleep(1.5)


run(Path(sys.argv[1]), Path(sys.argv[2]), "elf-variants", EMITS, size=(190, 42), prep=prep)
