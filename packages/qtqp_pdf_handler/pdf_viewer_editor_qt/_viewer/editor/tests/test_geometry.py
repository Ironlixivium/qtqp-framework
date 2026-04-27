from pdf_viewer_editor_qt._viewer.editor.geometry import PtPoint, PtRect


def test_pt_rect_normalized_makes_size_positive() -> None:
    r = PtRect(10, 20, -3, -4).normalized()
    assert r.w >= 0
    assert r.h >= 0
    assert r.x == 7
    assert r.y == 16


def test_pt_rect_contains() -> None:
    r = PtRect(0, 0, 10, 10)
    assert r.contains(PtPoint(0, 0))
    assert r.contains(PtPoint(10, 10))
    assert not r.contains(PtPoint(-1, 0))
    assert not r.contains(PtPoint(0, 11))


def test_pt_rect_iter_and_list_roundtrip() -> None:
    r = PtRect(1, 2, 3, 4)
    assert list(r) == [1, 2, 3, 4]
    assert PtRect.from_list(r.to_list()) == r


def test_pt_rect_from_list_requires_four() -> None:
    try:
        PtRect.from_list([1, 2, 3])
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for short list")

