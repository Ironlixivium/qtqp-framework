from qtqp.pdf_handler._viewer.editor.markups import RectMarkup
from qtqp.pdf_handler._viewer.editor.markups._typing import RectMarkupDict


def test_rect_markup_from_dict_uses_defaults_on_missing_and_invalid_fields() -> None:
    d: RectMarkupDict = {
        "id": "a",
        "page_index": 0,
        "rect": [1.0, 2.0, 3.0, 4.0],
        "kind": "rect",
        "stroke_color": [255, 0, 0, 255],
        "stroke_width": "nope",  # type: ignore[typeddict-item]
        "fill_color": [0, 0, 0, 0],
    }
    m = RectMarkup.from_dict(d)
    # Invalid stroke_width falls back to the default configured in from_dict.
    assert m.stroke_width == 1.0

