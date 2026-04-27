"""Viewer state types.

Keep this module free of heavy UI logic. It should only define the state the
widget tracks/exposes and a couple of small helpers (clamping/normalization).
"""


from dataclasses import dataclass, replace
from enum import Enum, auto
from typing import Self


class FitMode(Enum):
    """How the viewer chooses zoom."""

    FREE = auto()  # user-controlled zoom
    FIT_WIDTH = auto()  # zoom so page width fits viewport
    FIT_PAGE = auto()  # zoom so whole page fits viewport


class LayoutMode(Enum):
    """How the viewer lays out pages in the scene."""

    SINGLE = auto()  # conceptually single page; implementation may still stack
    CONTINUOUS = auto()  # vertical continuous scroll
    TWO_UP = auto()  # spreads (two pages per row)


def _clamp(v: float, lo: float, hi: float) -> float:
    """Clamp ``v`` to the inclusive range [lo, hi]."""
    return max(lo, min(hi, v))


def _normalize_rotation(deg: int) -> int:
    """Normalize rotation to a multiple of 90 degrees in [0, 360)."""
    # Force to nearest multiple of 90 and normalize into [0, 270]
    snapped = int(round(deg / 90.0) * 90)
    return snapped % 360


@dataclass(frozen=True, slots=True)
class ViewState:
    """State the widget uses for layout/interaction.

    page_index: 0-based
    zoom: scalar applied in the view transform
    rotation_deg: 0/90/180/270
    """

    page_index: int = 0
    zoom: float = 1.0
    rotation_deg: int = 0
    fit_mode: FitMode = FitMode.FREE
    layout_mode: LayoutMode = LayoutMode.CONTINUOUS

    min_zoom: float = 0.1
    max_zoom: float = 8.0

    page_spacing_pt: float = 12.0
    margin_pt: float = 0.0

    def with_page(self, page_index: int) -> Self:
        """Return a copy with an updated (clamped) page index."""
        return replace(self, page_index=max(0, page_index))

    def with_zoom(self, zoom: float, *, fit_mode: FitMode | None = None) -> Self:
        """Return a copy with an updated (clamped) zoom and fit mode."""
        z = _clamp(float(zoom), self.min_zoom, self.max_zoom)
        if fit_mode is None:
            fit_mode = self.fit_mode
        return replace(self, zoom=z, fit_mode=fit_mode)

    def with_rotation(self, rotation_deg: int) -> Self:
        """Return a copy with a normalized rotation."""
        return replace(self, rotation_deg=_normalize_rotation(rotation_deg))

    def with_fit_mode(self, fit_mode: FitMode) -> Self:
        """Return a copy with an updated fit mode."""
        return replace(self, fit_mode=fit_mode)

    def with_layout_mode(self, layout_mode: LayoutMode) -> Self:
        """Return a copy with an updated layout mode."""
        return replace(self, layout_mode=layout_mode)
