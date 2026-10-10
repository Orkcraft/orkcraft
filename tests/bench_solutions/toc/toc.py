from src.anchors import unique_anchors
from src.headings import headings
from src.outline import bullets


def toc(markdown):
    hs = headings(markdown)
    first = next((i for i, (lvl, _) in enumerate(hs) if lvl == 1), None)
    if first is not None:
        hs = hs[:first] + hs[first + 1:]
    return bullets([(lvl, t, a) for (lvl, t), a in zip(hs, unique_anchors([t for _, t in hs]))])
