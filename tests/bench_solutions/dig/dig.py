import re

TOKEN = re.compile(r'\.?([A-Za-z_][A-Za-z0-9_]*)|\[(-?\d+)\]|\["([^"]*)"\]')


def _path(path):
    if not path:
        raise ValueError(path)
    keys, pos = [], 0
    while pos < len(path):
        m = TOKEN.match(path, pos)
        if not m or (pos == 0 and path[0] == "."):
            raise ValueError(path)
        keys.append(int(m[2]) if m[2] is not None else m[1] if m[1] is not None else m[3])
        pos = m.end()
    return keys


def dig(data, path, default=None):
    for key in _path(path):
        try:
            if isinstance(key, int) != isinstance(data, list):
                return default
            data = data[key]
        except (KeyError, IndexError, TypeError):
            return default
    return data


def put(data, path, value):
    keys = _path(path)
    for key, nxt in zip(keys, keys[1:]):
        empty = [] if isinstance(nxt, int) else {}
        if isinstance(key, int):
            while len(data) <= key:
                data.append(None)
            if data[key] is None:
                data[key] = empty
        else:
            data.setdefault(key, empty)
        data = data[key]
    last = keys[-1]
    if isinstance(last, int):
        while len(data) <= last:
            data.append(None)
    data[last] = value
