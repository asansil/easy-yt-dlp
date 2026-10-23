"""Version numbers as used by the package (PEP 440) and the release tags.

pyproject: 2.0.0, 2.0.0b1, 2.0.0rc2, 2.0.0.dev0
tags:      v2.0.0, v2.0.0-beta.1, v2.0.0-rc.2
"""

import re
from functools import total_ordering

_RE = re.compile(
    r"^v?(?P<release>\d+(?:\.\d+)*)"
    r"(?:[-.]?(?P<pre>a|alpha|b|beta|rc|c|dev)[-.]?(?P<number>\d+)?)?$",
    re.IGNORECASE,
)
# Ordering of pre-release kinds; a final release sorts after all of them.
_KIND_RANK = {"dev": 0, "a": 1, "b": 2, "rc": 3}
_ALIASES = {"alpha": "a", "beta": "b", "c": "rc"}


@total_ordering
class Version:
    def __init__(self, text: str) -> None:
        match = _RE.match(text.strip())
        if not match:
            raise ValueError(f"Not a version: {text!r}")
        parts = [int(p) for p in match.group("release").split(".")]
        while len(parts) < 3:
            parts.append(0)
        self.release = tuple(parts)
        kind = (match.group("pre") or "").lower()
        self.kind = _ALIASES.get(kind, kind)
        self.number = int(match.group("number") or 0)

    @property
    def is_prerelease(self) -> bool:
        return bool(self.kind)

    def _key(self) -> tuple:
        rank = _KIND_RANK[self.kind] if self.kind else 4
        return (self.release, rank, self.number)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Version) and self._key() == other._key()

    def __lt__(self, other: "Version") -> bool:
        return self._key() < other._key()

    def __hash__(self) -> int:
        return hash(self._key())

    def pep440(self) -> str:
        base = ".".join(str(p) for p in self.release)
        if not self.kind:
            return base
        if self.kind == "dev":
            return f"{base}.dev{self.number}"
        return f"{base}{self.kind}{self.number}"

    def tag(self) -> str:
        base = "v" + ".".join(str(p) for p in self.release)
        names = {"a": "alpha", "b": "beta", "rc": "rc", "dev": "dev"}
        return f"{base}-{names[self.kind]}.{self.number}" if self.kind else base

    def __str__(self) -> str:
        return self.pep440()

    def __repr__(self) -> str:
        return f"Version({self.pep440()!r})"


def parse(text: str) -> Version | None:
    try:
        return Version(text)
    except ValueError:
        return None
