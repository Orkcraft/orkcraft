from collections import OrderedDict


class LRUCache:
    def __init__(self, capacity, on_evict=None):
        if capacity < 1:
            raise ValueError(capacity)
        self.capacity, self.on_evict, self.data = capacity, on_evict, OrderedDict()

    def put(self, key, value):
        self.data[key] = value
        self.data.move_to_end(key)
        while len(self.data) > self.capacity:
            k, v = self.data.popitem(last=False)
            if self.on_evict:
                self.on_evict(k, v)

    def get(self, key, default=None):
        if key not in self.data:
            return default
        self.data.move_to_end(key)
        return self.data[key]

    def peek(self, key, default=None):
        return self.data.get(key, default)

    def __len__(self):
        return len(self.data)

    def __contains__(self, key):
        return key in self.data
