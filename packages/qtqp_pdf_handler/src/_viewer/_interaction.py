"""Input mapping for the PDF viewer.

This module maps raw input events to *intent* signals.
It does not directly manipulate the scene or render pages.

Typical mapping (customize as you like):
- Ctrl + mouse wheel: zoom in/out
- PageUp/PageDown: previous/next page
- Ctrl+0: fit page, Ctrl+2: fit width, Ctrl+1: actual size
- Hold Space: pan (hand drag)
"""

from collections.abc import Callable
from typing import Literal, cast

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QFocusEvent, QKeyEvent, QWheelEvent, QWindowStateChangeEvent
from PySide6.QtWidgets import QGraphicsTextItem, QGraphicsView, QWidget
from qtqp.signals import QSignal

from ._state import FitMode


class PdfInteractionController(QObject):
    """Event filter that converts input into high-level viewer commands."""

    # Zoom multipliers (e.g. 1.1 for zoom in, 1/1.1 for zoom out)
    zoom_relative_requested: QSignal[float]   = QSignal[float](float, qt_signal=True)

    # Set absolute zoom factor (fit_mode handled separately)
    zoom_absolute_requested: QSignal[float]   = QSignal[float](float, qt_signal=True)

    # Navigation
    page_step_requested:  QSignal[int]        = QSignal[int](int, qt_signal=True)    # +1/-1
    go_to_page_requested: QSignal[int]        = QSignal[int](int, qt_signal=True)    # 0-based; -1 means "last"

    # Fit modes
    fit_mode_requested: QSignal[FitMode]      = QSignal[FitMode](object, qt_signal=True)

    # Pan/hand-drag mode
    pan_mode_requested: QSignal[bool]         = QSignal[bool](bool, qt_signal=True)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._zoom_step = 1.1
        self._wheel_zoom_scale = 0.1
        self._space_down = False

    def attach(self, widget: QObject) -> None:
        """Install this controller as an event filter on the viewport widget."""
        widget.installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        match event:
            case QWheelEvent():
                return self._handle_wheel_roll(event)
            case QKeyEvent():
                if self._is_text_editing_active(watched):
                    return False
                return self._handle_key_press(event)
            case QFocusEvent():
                if event.type() == QEvent.Type.FocusOut:
                    return self._focus_lost()
                return False
            case QWindowStateChangeEvent():
                if event.type() == QEvent.Type.WindowDeactivate:
                    return self._focus_lost()
                return False
            case _:
                return False

    def _focus_lost(self) -> Literal[False]:
        if self._space_down:
            self._space_down = False
            self.pan_mode_requested.emit(False)
        return False

    def _is_text_editing_active(self, watched: QObject) -> bool:
        view = watched if isinstance(watched, QGraphicsView) else cast(QGraphicsView, watched.parent())
        focus_item = view.scene().focusItem()
        if isinstance(focus_item, QGraphicsTextItem):
            flags = focus_item.textInteractionFlags()
            return bool(flags & Qt.TextInteractionFlag.TextEditorInteraction)
        return False

    def _handle_key_press(self, event: QKeyEvent) -> bool:
        key = event.key()
        mods = event.modifiers()

        # Common viewer shortcuts
        if mods & Qt.KeyboardModifier.ControlModifier:
            if key == Qt.Key.Key_0:
                self.fit_mode_requested.emit(FitMode.FIT_PAGE)
                return True
            elif key == Qt.Key.Key_2:
                self.fit_mode_requested.emit(FitMode.FIT_WIDTH)
                return True
            elif key == Qt.Key.Key_1:
                self.zoom_absolute_requested.emit(1.0)
                self.fit_mode_requested.emit(FitMode.FREE)
                return True

        key_actions: dict[int, Callable[[], bool | None]] = {
            Qt.Key.Key_Plus: lambda: self.zoom_relative_requested.emit(self._zoom_step),
            Qt.Key.Key_Equal: lambda: self.zoom_relative_requested.emit(self._zoom_step),
            Qt.Key.Key_Minus: lambda: self.zoom_relative_requested.emit(1.0 / self._zoom_step),
            Qt.Key.Key_PageDown: lambda: self.page_step_requested.emit(+1),
            Qt.Key.Key_PageUp: lambda: self.page_step_requested.emit(-1),
            Qt.Key.Key_Home: lambda: self.go_to_page_requested.emit(0),
            Qt.Key.Key_End: lambda: self.go_to_page_requested.emit(-1),
            Qt.Key.Key_Space: lambda: self._handle_space_press(event),
        }

        if key in key_actions.keys():
            result = key_actions[key]()
            if result is not None:
                return result
            else:
                return True

        return False

    def _handle_space_press(self, event: QKeyEvent) -> bool:
        if event.isAutoRepeat():
            return True
        if event.type() == event.Type.KeyPress:
            self._space_down = True
            self.pan_mode_requested.emit(True)
        else:
            self._space_down = False
            self.pan_mode_requested.emit(False)

        return True

    def _handle_wheel_roll(self, event: QWheelEvent) -> bool:
        mods = event.modifiers()
        if mods & Qt.KeyboardModifier.ControlModifier:
            dy = event.angleDelta().y()
            if dy == 0:
                dy = event.pixelDelta().y()
            if dy == 0:
                return False
            steps = dy / 120.0
            exponent = steps * self._wheel_zoom_scale
            factor = self._zoom_step**exponent
            self.zoom_relative_requested.emit(factor)
            return True
        return False
