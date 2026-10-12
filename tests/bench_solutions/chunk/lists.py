def chunk(items, size):
    if size < 1:
        raise ValueError(size)
    items = list(items)
    return [items[i:i + size] for i in range(0, len(items), size)]
