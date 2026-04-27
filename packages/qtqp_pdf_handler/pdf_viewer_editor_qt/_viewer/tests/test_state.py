from pdf_viewer_editor_qt._viewer._state import FitMode, LayoutMode, ViewState


def test_view_state_with_zoom_clamps() -> None:
    s = ViewState(min_zoom=0.5, max_zoom=2.0)
    assert s.with_zoom(0.1).zoom == 0.5
    assert s.with_zoom(10.0).zoom == 2.0


def test_view_state_rotation_normalizes() -> None:
    s = ViewState()
    assert s.with_rotation(91).rotation_deg == 90
    assert s.with_rotation(-90).rotation_deg == 270


def test_view_state_modes_round_trip() -> None:
    s = ViewState().with_fit_mode(FitMode.FIT_WIDTH).with_layout_mode(LayoutMode.TWO_UP).with_page(3)
    assert s.fit_mode == FitMode.FIT_WIDTH
    assert s.layout_mode == LayoutMode.TWO_UP
    assert s.page_index == 3

