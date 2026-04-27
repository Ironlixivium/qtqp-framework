"""Point and rectangle geometry primitives in PDF space."""

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Self


@dataclass(frozen=True, slots=True)
class PtPoint:
    """A point in PDF coordinate space (points)."""

    x: float
    y: float


@dataclass(frozen=True, slots=True)
class PtRect:
    """An axis-aligned rectangle in PDF coordinate space (points)."""

    x: float
    y: float
    w: float
    h: float

    def normalized(self) -> Self:
        """Return a copy with non-negative width/height."""
        x, y, w, h = float(self.x), float(self.y), float(self.w), float(self.h)
        if w < 0:
            x += w
            w = -w
        if h < 0:
            y += h
            h = -h
        return type(self)(x, y, w, h)

    def contains(self, point: PtPoint) -> bool:
        """Return True if ``point`` lies within this rect (inclusive bounds)."""
        return (self.x <= point.x <= self.x + self.w) and (self.y <= point.y <= self.y + self.h)

    def __iter__(self) -> Iterator[float]:
        """Iterate as ``(x, y, w, h)`` for Qt convenience APIs."""
        yield self.x
        yield self.y
        yield self.w
        yield self.h

    def to_list(self) -> list[float]:
        """Serialize as ``[x, y, w, h]`` floats."""
        return [float(self.x), float(self.y), float(self.w), float(self.h)]

    @classmethod
    def from_list(cls, li: list[float]) -> Self:
        """Parse a rect from ``[x, y, w, h]``."""
        if len(li) < 4:
            raise ValueError(li)
        return cls(float(li[0]), float(li[1]), float(li[2]), float(li[3]))
