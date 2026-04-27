"""Page layout logic for PdfScene.

This module is intentionally UI-agnostic: it computes page rectangles in scene
coordinates (points), given page sizes and a layout mode.
"""


from collections.abc import Sequence

from PySide6.QtCore import QRectF, QSizeF

from ._state import LayoutMode


def compute_page_rects(
    page_sizes_pt: Sequence[QSizeF],
    mode: LayoutMode,
    *,
    spacing_pt: float = 12.0,
    margin_pt: float = 12.0,
) -> list[QRectF]:
    """Compute a QRectF per page, in scene coordinates (points).

    The returned list is indexed by page_index.

    Notes:
    - For LayoutMode.SINGLE, pages are still positioned in a vertical stack.
      The widget may decide to hide non-current pages if desired.
    """

    if not page_sizes_pt:
        return []

    if mode in (LayoutMode.SINGLE, LayoutMode.CONTINUOUS):
        rects: list[QRectF] = []
        y = margin_pt
        max_w = 0.0
        for size in page_sizes_pt:
            w = float(size.width())
            h = float(size.height())
            rects.append(QRectF(margin_pt, y, w, h))
            y += h + spacing_pt
            max_w = max(max_w, w)
        return rects

    if mode == LayoutMode.TWO_UP:
        rects = [QRectF() for _ in page_sizes_pt]
        y = margin_pt
        i = 0
        while i < len(page_sizes_pt):
            left = page_sizes_pt[i]
            right = page_sizes_pt[i + 1] if i + 1 < len(page_sizes_pt) else None

            lw = float(left.width())
            lh = float(left.height())

            if right is not None:
                rw = float(right.width())
                rh = float(right.height())
            else:
                rw = rh = 0.0

            row_h = max(lh, rh)

            # Place left page
            rects[i] = QRectF(margin_pt, y, lw, lh)

            # Place right page, aligned to top of row
            if right is not None:
                x2 = margin_pt + lw + spacing_pt
                rects[i + 1] = QRectF(x2, y, rw, rh)

            y += row_h + spacing_pt
            i += 2

        return rects

    # Future-proof default: fall back to continuous.
    return compute_page_rects(
        page_sizes_pt,
        LayoutMode.CONTINUOUS,
        spacing_pt=spacing_pt,
        margin_pt=margin_pt,
    )


def scene_bounding_rect(page_rects: Sequence[QRectF], *, margin_pt: float = 12.0) -> QRectF:
    """Compute a bounding rect for all pages, with a little extra margin."""
    if not page_rects:
        return QRectF(0, 0, 0, 0)

    r = page_rects[0]
    left = r.left()
    top = r.top()
    right = r.right()
    bottom = r.bottom()

    for pr in page_rects[1:]:
        left = min(left, pr.left())
        top = min(top, pr.top())
        right = max(right, pr.right())
        bottom = max(bottom, pr.bottom())

    return QRectF(
        left - margin_pt,
        top - margin_pt,
        (right - left) + 2 * margin_pt,
        (bottom - top) + 2 * margin_pt,
    )
