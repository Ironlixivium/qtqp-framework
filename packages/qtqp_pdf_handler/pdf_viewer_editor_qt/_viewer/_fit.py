"""Fit-mode zoom calculations.

Pure functions: no Qt widgets, no state mutation.
"""

from PySide6.QtCore import QRectF, QSizeF

from ._state import FitMode


def compute_fit_zoom(fit_mode: FitMode, page_rect: QRectF, viewport_size: QSizeF) -> float:
    """Return the zoom scalar that satisfies *fit_mode* for the given page/viewport.

    Args:
        fit_mode: FIT_WIDTH or FIT_PAGE (FREE callers should not call this).
        page_rect: Page bounding rect in scene/page-item coordinates.
        viewport_size: Current viewport widget size in pixels.

    Returns:
        float: Computed zoom scalar, or None if fit_mode is FREE.
    """
    if fit_mode == FitMode.FREE:
        raise ValueError(fit_mode)

    vw = max(1.0, float(viewport_size.width()))
    vh = max(1.0, float(viewport_size.height()))
    pw = max(1.0, float(page_rect.width()))
    ph = max(1.0, float(page_rect.height()))

    if fit_mode == FitMode.FIT_WIDTH:
        return (vw - 2) / pw
    else:  # FIT_PAGE
        return min((vw - 2) / pw, (vh - 2) / ph)
