from collections import defaultdict
from src.csvin import read_rows
from src.dates import month_of
from src.money import format_money, parse_money
def monthly_report(path):
    t = defaultdict(int)
    for r in read_rows(path): t[(month_of(r["date"]), r["category"])] += parse_money(r["amount"])
    keys = sorted(t); cw = max(len(c) for _, c in keys); aw = max(len(format_money(v)) for v in t.values())
    return "\n".join(f"{m}  {c.ljust(cw)}  {format_money(t[(m, c)]).rjust(aw)}" for m, c in keys)
