from qtqp.pdf_handler._color import Color


def test_color_validates_channels() -> None:
    Color(red=0, green=0, blue=0, alpha=0)
    Color(red=255, green=255, blue=255, alpha=255)


def test_color_invalid_channel_raises() -> None:
    try:
        Color(red=-1, green=0, blue=0, alpha=0)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for invalid channel")


def test_color_from_rgba_sequence() -> None:
    c = Color.from_rgba([1, 2, 3, 4])
    assert c.rgba == (1, 2, 3, 4)

