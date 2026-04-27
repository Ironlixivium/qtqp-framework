from functools import cached_property

from PySide6.QtCore import QTimer
from q_signalkit import QSignalInstance


class _Signals:
    def __init__(self, q_timer: QTimer) -> None:
        self._timer = q_timer

    @cached_property
    def interval_elapsed(self) -> QSignalInstance[()]:
        signal_instance = QSignalInstance[()]()
        self._timer.timeout.connect(signal_instance.emit)
        return signal_instance





class Timer:
    def __init__(self, interval_msec: int, /, *, repeating: bool = False) -> None:
        self.qt_timer = QTimer()
        
        if not repeating:
            self.qt_timer.setSingleShot(True)

        self.signals = _Signals(self.qt_timer)