"""Domain color type with Qt conversion helpers."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Self

from PySide6.QtGui import QColor


@dataclass(frozen=True, slots=True)
class Color:
    """An RGBA color with byte channels.

    Attributes
    ----------
    red, green, blue, alpha:
        Integer channels in the inclusive range 0..255.
    """

    red: int
    green: int
    blue: int
    alpha: int

    def __post_init__(self) -> None:
        """Validate channel ranges."""
        for field, value in (("Red", self.red), ("Green", self.green), ("Blue", self.blue), ("Alpha", self.alpha)):
            if not 0 <= value <= 255:
                raise ValueError(f"Color.{field} must be 0-255, got {value}")

    @classmethod
    def from_rgba(cls, rgba: Sequence[int]) -> Self:
        """Create from a 4-element ``(r, g, b, a)`` sequence."""
        if len(rgba) < 4:
            raise ValueError(rgba)
        return cls(red=rgba[0], green=rgba[1], blue=rgba[2], alpha=rgba[3])

    @property
    def rgba(self) -> tuple[int, int, int, int]:
        """Return ``(r, g, b, a)`` as 0..255 ints."""
        return self.red, self.green, self.blue, self.alpha

    @property
    def q_color(self) -> QColor:
        """Convert to a ``QColor``."""
        return QColor(self.red, self.green, self.blue, self.alpha)

    @property
    def rgb_float(self) -> tuple[float, float, float]:
        """Return normalized RGB in 0..1 space (alpha excluded)."""
        return self.red / 255, self.green / 255, self.blue / 255
    
    @property
    def alpha_float(self) -> float:
        """Return normalized alpha in 0..1 space."""
        return self.alpha / 255
