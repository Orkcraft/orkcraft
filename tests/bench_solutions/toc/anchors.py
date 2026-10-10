import re


def anchor(text):
    text = text.strip().lower().replace("`", "")
    text = re.sub(r"[^\w\- ]", "", text)
    return text.replace(" ", "-")


def unique_anchors(texts):
    seen, out = {}, []
    for t in texts:
        a = anchor(t)
        n = seen.get(a, 0)
        out.append(a if n == 0 else f"{a}-{n}")
        seen[a] = n + 1
    return out
