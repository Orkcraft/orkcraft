import time
class TokenBucket:
    def __init__(self, rate, capacity, clock=time.monotonic):
        if rate <= 0 or capacity <= 0: raise ValueError("rate and capacity must be positive")
        self.rate, self.capacity, self.clock = rate, capacity, clock
        self.tokens, self.at = float(capacity), clock()
    def _fill(self):
        now = self.clock(); self.tokens = min(self.capacity, self.tokens + (now - self.at) * self.rate); self.at = now
    def _check(self, n):
        if n < 0 or n > self.capacity: raise ValueError("n")
    def available(self):
        self._fill(); return self.tokens
    def take(self, n=1):
        self._check(n); self._fill()
        if self.tokens + 1e-9 >= n: self.tokens -= n; return True
        return False
    def wait_time(self, n=1):
        self._check(n); self._fill(); return max(0.0, (n - self.tokens) / self.rate)
