def _check(intervals):
    for a, b in intervals:
        if b < a:
            raise ValueError((a, b))


def merge(intervals):
    _check(intervals)
    out = []
    for a, b in sorted(i for i in intervals if i[1] > i[0]):
        if out and a <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def subtract(intervals, holes):
    out = []
    holes = merge(holes)
    for a, b in merge(intervals):
        for h0, h1 in holes:
            if h1 <= a or h0 >= b:
                continue
            if h0 > a:
                out.append((a, h0))
            a = max(a, h1)
            if a >= b:
                break
        if a < b:
            out.append((a, b))
    return merge(out)


def total(intervals):
    return sum(b - a for a, b in merge(intervals))
