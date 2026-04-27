"""
signalkit — type-safe synchronous signals for Python.

Core API::

    from q_signalkit import QSignal, QSignalInstance

The optional Slot replacement QSlot lives in q_signalkit._qt_slot and is only needed in
projects that use PySide6.
"""
from ._signal import QSignal, QSignalInstance

__all__ = [
    "QSignal",
    "QSignalInstance",
]
