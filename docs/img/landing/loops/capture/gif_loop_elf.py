import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import giflib
from giflib import run, emit, open_building

giflib.SIM["work"] = "hero-b.md: warmer CTA, 'Start free'"
giflib.SIM["draft"] = "# Hero B\n\n[ Start free ]\n\nwarmer CTA · focus order fixed · contrast 4.8:1"


def reject_a(app):
    from orkcraft.screens.typed.generator_view import GeneratorView
    for v in app.query(GeneratorView):
        v.reject("hero-a.md")


TIMELINE = [
    (0.3, emit("pit", "pit.text", "Hero section, 3 variants: warmer CTA", "brief")),
    (3.0, reject_a),
    (4.0, open_building("lake")),
]
for mode, texts in run(Path(sys.argv[1]), Path(sys.argv[2]), "elf-variants", TIMELINE, seconds=5.0, size=(190, 42)):
    print(f"--- {mode} last\n" + "\n".join(texts[-1].splitlines()[:14]))
