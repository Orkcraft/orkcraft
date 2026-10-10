"""A tiny inventory: items, their counts, and a report."""
import json


class Inventory:
    def __init__(self):
        self.items = {}

    def add(self, name, count=1):
        self.items[name] = self.items.get(name, 0) + count

    def remove(self, name, count=1):
        left = self.items.get(name, 0) - count
        if left < 0:
            raise ValueError(name)
        if left == 0:
            self.items.pop(name, None)
        else:
            self.items[name] = left

    def report(self):
        return "\n".join(f"{k}: {v}" for k, v in sorted(self.items.items()))

    def save(self, path):
        with open(path, "w") as f:
            json.dump(self.items, f)

    @classmethod
    def load(cls, path):
        inv = cls()
        with open(path) as f:
            inv.items = json.load(f)
        return inv
