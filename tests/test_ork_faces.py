"""An ork's face says its role, never its building (docs/design/ork-icons.md §6): every ork of TERMS has a face in
js/icons.js FACES, every face is cut by tools/camp_faces.py, and its files exist at their sizes."""
import json
import re
import struct
from pathlib import Path

from orkcraft.realm.lexicon import TERMS

ROOT = Path(__file__).resolve().parent.parent
ICONS = (ROOT / "orkcraft/gui/static/js/icons.js").read_text(encoding="utf-8")
FACES_DIR = ROOT / "design-system/sprites/camp/orks/faces"
SPEC = json.loads((ROOT / "tools/camp_sheets.json").read_text(encoding="utf-8"))["faces"]
BODIES = ["warchief", "grunt", "quartermaster", "seer", "mason", "alchemist", "mechanic", "treasurer", "pathfinder",
          "taskmaster", "lookout", "loader", "farseer", "warder", "artisan"]


def size(path: Path) -> tuple[int, int]:
    """A PNG's width and height, from its header (no Pillow in the town's dependencies)."""
    return struct.unpack(">II", path.read_bytes()[16:24])


def faces() -> dict[str, str]:
    block = re.search(r"export const FACES = \{(.*?)\n\};", ICONS, re.S).group(1)
    return dict(re.findall(r"([a-z_]+): \"([a-z-]+)\"", block))


def test_every_ork_of_terms_has_a_face():
    keys = {t.key.split(".", 1)[1] for t in TERMS if t.key.startswith("orc.")}
    missing = keys - set(faces())
    assert not missing, f"orks with no face in js/icons.js FACES: {sorted(missing)}"


def test_every_face_is_cut_and_its_files_exist():
    for role in set(faces().values()):
        assert role in SPEC["roles"], f"{role}: not in tools/camp_sheets.json faces.roles"
        assert size(FACES_DIR / f"{role}.png") == (32, 24)
        assert size(FACES_DIR / f"{role}-16.png") == (16, 16)


def test_the_bodies_have_their_own_faces_and_no_role_borrows_one():
    plain = (FACES_DIR / "plain.png").read_bytes()
    for role in BODIES:
        assert (ROOT / f"design-system/sprites/camp/orks/roles/{role}.png").exists()
        assert (FACES_DIR / f"{role}.png").read_bytes() != plain, f"{role} has a body but wears the plain head"
    own = {(FACES_DIR / f"{r}.png").read_bytes() for r in BODIES}
    assert len(own) == len(BODIES), "two roles share a face"
    for role in set(SPEC["roles"]) - set(BODIES):
        assert (FACES_DIR / f"{role}.png").read_bytes() == plain, f"{role} has no body: the plain head, never a borrowed face"


def test_a_face_by_role_not_by_building():
    f = faces()
    assert f["town_hall"] == "warchief" and f["barracks"] == "grunt" and f["loot"] == "quartermaster"
    assert f["lake"] == "seer" and f["lab"] == "mechanic" and f["ux_lab"] == "alchemist"
    assert "StewardHead" not in ICONS                       # the hat by building is gone from the interface
