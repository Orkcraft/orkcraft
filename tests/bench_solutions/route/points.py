def parse_point(text):
    parts = text.split(",")
    if len(parts) != 2:
        raise ValueError(text)
    lat, lon = (float(p) for p in parts)
    if abs(lat) > 90 or abs(lon) > 180:
        raise ValueError(text)
    return lat, lon
