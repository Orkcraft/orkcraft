import re
def format_money(c):
    s = "-" if c < 0 else ""; c = abs(c); return f"{s}{c // 100:,}.{c % 100:02d}"
def parse_money(t):
    m = re.fullmatch(r"(-?)(\d{1,3}(?:,\d{3})*|\d+)(?:\.(\d{1,2}))?", t.strip())
    if not m: raise ValueError(t)
    c = int(m[2].replace(",", "")) * 100 + int((m[3] or "0").ljust(2, "0")); return -c if m[1] else c
