from src.geo import distance_km
from src.points import parse_point
from src.units import human_distance


def route_length(text):
    pts = [parse_point(ln) for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    legs = list(zip(pts, pts[1:]))
    return f"{human_distance(sum(distance_km(a, b) for a, b in legs))} over {len(legs)} legs"
