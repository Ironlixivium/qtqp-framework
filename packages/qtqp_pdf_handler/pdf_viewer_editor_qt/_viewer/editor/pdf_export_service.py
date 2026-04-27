"""Export annotated PDFs using PyMuPDF."""


from collections.abc import Callable
from pathlib import Path

import fitz

from .geometry import PtRect
from .markups import Markup, RectMarkup, StampMarkup, TextBoxMarkup


def export_pdf(
    *,
    source_pdf_bytes: bytes,
    annotations: list[Markup],
    resolve_stamp_path: Callable[[str], Path | None],
    output_path: str | Path,
) -> Path:
    doc = fitz.open(stream=source_pdf_bytes, filetype="pdf")
    try:
        annotations_by_page: dict[int, list[Markup]] = {}
        for ann in annotations:
            annotations_by_page.setdefault(ann.page_index, []).append(ann)

        for page_index in range(doc.page_count):
            page = doc.load_page(page_index)
            for ann in annotations_by_page.get(page_index, []):
                _apply_annotation(page, ann, resolve_stamp_path)

        out_path = Path(output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(out_path))
        return out_path
    finally:
        doc.close()


def _apply_annotation(
    page: fitz.Page,
    markup: Markup,
    resolve_stamp_path: Callable[[str], Path | None],
) -> None:
    if isinstance(markup, RectMarkup):
        _draw_rect(page, markup)
    elif isinstance(markup, TextBoxMarkup):
        _draw_text_box(page, markup)
    elif isinstance(markup, StampMarkup):
        _draw_stamp(page, markup, resolve_stamp_path)


def _draw_rect(page: fitz.Page, markup: RectMarkup) -> None:
    rect = _rect_to_fitz(markup.rect)
    page.draw_rect(
        rect,
        color=markup.stroke_color.rgb_float,
        width=markup.stroke_width,
        stroke_opacity=markup.stroke_color.alpha_float,
        fill=markup.fill_color.rgb_float,
        fill_opacity=markup.fill_color.alpha_float,
    )


def _draw_text_box(page: fitz.Page, markup: TextBoxMarkup) -> None:
    rect = markup.rect.normalized()
    padding = markup.padding
    inset_w = max(0.0, rect.w - (padding * 2.0))
    inset_h = max(0.0, rect.h - (padding * 2.0))
    text_rect = fitz.Rect(
        rect.x + padding,
        rect.y + padding,
        rect.x + padding + inset_w,
        rect.y + padding + inset_h,
    )
    page.insert_textbox(
        text_rect,
        markup.text,
        fontsize=markup.font_size,
        fontname="helv",
    )


def _draw_stamp(
    page: fitz.Page,
    markup: StampMarkup,
    resolve_stamp_path: Callable[[str], Path | None],
) -> None:
    stamp_path = resolve_stamp_path(markup.stamp_asset_id)
    if stamp_path is None or not stamp_path.exists():
        return
    image_bytes = stamp_path.read_bytes()
    rect = _rect_to_fitz(markup.rect)
    if markup.opacity >= 0.999:
        page.insert_image(rect, stream=image_bytes)
        return
    pixmap = fitz.Pixmap(stream=image_bytes)
    if not pixmap.alpha:
        pixmap = fitz.Pixmap(pixmap, 1)
    alpha_value = max(0, min(255, int(round(markup.opacity * 255))))
    pixmap.set_alpha(bytes(alpha_value))
    page.insert_image(rect, pixmap=pixmap)


def _rect_to_fitz(rect: PtRect) -> fitz.Rect:
    normalized = rect.normalized()
    return fitz.Rect(
        normalized.x,
        normalized.y,
        normalized.x + normalized.w,
        normalized.y + normalized.h,
    )
