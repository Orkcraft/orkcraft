def mean(values):
    if not values:
        raise ValueError("empty")
    return sum(values) / len(values)


def median(values):
    if not values:
        raise ValueError("empty")
    s, n = sorted(values), len(values)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2
