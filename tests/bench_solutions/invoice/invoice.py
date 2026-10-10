from src.discounts import apply_code
from src.lines import parse_line
from src.tax import tax


def _m(c):
    return f"{'-' if c < 0 else ''}{abs(c) // 100}.{abs(c) % 100:02d}"


def invoice(text, region, code):
    items = [parse_line(ln) for ln in text.splitlines() if ln.strip()]
    w = max(len(n) for n, *_ in items)
    qw = max(len(str(q)) for _, q, _ in items)
    aw = max(len(_m(q * p)) for _, q, p in items)
    lines = [f"{n.ljust(w)}  {str(q).rjust(qw)}  {_m(q * p).rjust(aw)}" for n, q, p in items]
    sub = sum(q * p for _, q, p in items)
    after = apply_code(sub, code)
    t = tax(after, region)
    rows = [("subtotal", sub), ("discount", after - sub), ("tax", t), ("total", after + t)]
    rw = max(len(_m(v)) for _, v in rows)
    return "\n".join(lines + [f"{k.ljust(8)}  {_m(v).rjust(rw)}" for k, v in rows])
