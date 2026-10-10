def parse_roster(text):
    out = {}
    for i, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, sep, scores = line.partition(":")
        try:
            if not sep or not name.strip():
                raise ValueError
            out[name.strip()] = [float(s) for s in scores.split(",")]
        except ValueError:
            raise ValueError(f"line {i}: {line}") from None
    return out
