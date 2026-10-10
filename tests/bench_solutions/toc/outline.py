def bullets(items):
    top = min((lvl for lvl, *_ in items), default=1)
    return "\n".join(f"{'  ' * (lvl - top)}- [{text}](#{a})" for lvl, text, a in items)
