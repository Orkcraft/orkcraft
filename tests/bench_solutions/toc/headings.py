import re

ATX = re.compile(r"^(#{1,6}) +(.*?)(?: +#+)? *$")


def headings(markdown):
    out, fenced = [], False
    for line in markdown.splitlines():
        if line.startswith("```"):
            fenced = not fenced
            continue
        m = None if fenced else ATX.match(line)
        if m:
            out.append((len(m[1]), m[2].strip()))
    return out
