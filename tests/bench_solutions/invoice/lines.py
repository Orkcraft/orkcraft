import re

LINE = re.compile(r"\s*(\d+)\s+x\s+(\S.*?)\s+@\s+(\d+)(?:\.(\d{1,2}))?\s*")


def parse_line(text):
    m = LINE.fullmatch(text)
    if not m or int(m[1]) < 1:
        raise ValueError(text)
    return m[2], int(m[1]), int(m[3]) * 100 + int((m[4] or "0").ljust(2, "0"))
