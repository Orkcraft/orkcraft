import re
from dataclasses import dataclass, field

NUM = r"(0|[1-9]\d*)"
IDENT = r"(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)"
RX = re.compile(rf"{NUM}\.{NUM}\.{NUM}(?:-({IDENT}(?:\.{IDENT})*))?(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?")


@dataclass(frozen=True)
class Version:
    major: int
    minor: int
    patch: int
    pre: tuple = ()
    build: str = field(default="", compare=False)

    def _key(self):
        pre = tuple((0, p, "") if isinstance(p, int) else (1, 0, p) for p in self.pre)
        return (self.major, self.minor, self.patch, not self.pre, pre)

    def __lt__(self, other):
        return self._key() < other._key()

    def __eq__(self, other):
        return self._key() == other._key()

    def __hash__(self):
        return hash(self._key())

    def __str__(self):
        s = f"{self.major}.{self.minor}.{self.patch}"
        if self.pre:
            s += "-" + ".".join(str(p) for p in self.pre)
        return s + (f"+{self.build}" if self.build else "")

    def bump(self, part):
        if part == "major":
            return Version(self.major + 1, 0, 0)
        if part == "minor":
            return Version(self.major, self.minor + 1, 0)
        return Version(self.major, self.minor, self.patch + 1)


def parse(text):
    m = RX.fullmatch(text or "")
    if not m:
        raise ValueError(text)
    pre = tuple(int(p) if p.isdigit() else p for p in m[4].split(".")) if m[4] else ()
    return Version(int(m[1]), int(m[2]), int(m[3]), pre, m[5] or "")
