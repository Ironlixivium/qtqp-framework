"""
Core signal primitives. No external dependencies.
"""
from __future__ import annotations

import weakref
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, Protocol, cast, overload, Self

if TYPE_CHECKING:
    from PySide6.QtCore import Signal

class _BoundMethod[*Types](Protocol):
    def __self__(self) -> None: ...
    def __func__(self) -> None: ...
    def __call__(self, *args: *Types) -> None: ...

@dataclass
class _BoundSlot[*Types]:
    """Weak reference to a bound method, with identity tracking for disconnect."""

    ref: weakref.ref[Any]
    obj_id: int
    func_id: int

    @classmethod
    def from_method(cls, method: _BoundMethod[*Types]) -> Self:
        return cls(
            ref=weakref.WeakMethod(method),
            obj_id=id(method.__self__),
            func_id=id(method.__func__),
        )

    def matches(self, method: _BoundMethod[*Types]) -> bool:
        return (
            id(method.__self__) == self.obj_id
            and id(method.__func__) == self.func_id
        )

    def call(self, *payload: *Types) -> bool:
        """Invoke the slot. Returns False if the weak reference is dead."""
        resolved = self.ref()
        if resolved is None:
            return False
        resolved(*payload)
        return True

class QSignalInstance[*Types]:
    """
    A type-safe, synchronous signal.

    Bound methods are held by weak reference — connecting a slot will not
    prevent its owner from being garbage collected. Plain callables (lambdas,
    free functions) are held by strong reference. Dead weak references are
    pruned automatically on emit.

    Note: Mutating connections from within a connected slot (connect/disconnect
    during emit) is not guaranteed to be safe. Avoid it.

    Usage as an instance attribute::

        class Watcher:
            def __init__(self) -> None:
                self.changed: QSignalInstance[str] = QSignalInstance()

        w = Watcher()
        w.changed.connect(some_handler)
        w.changed.emit("hello")

    Or as a class attribute via QSignal (see below).
    """

    def __init__(self) -> None:
        self._bound: list[_BoundSlot[*Types]] = []
        self._plain: list[Callable[[*Types], None]] = []

    def connect(self, slot: Callable[[*Types], None]) -> None:
        """Connect a callable. Python bound methods are stored as weak references.
        Builtin methods and plain callables are stored as strong references."""
        if hasattr(slot, "__func__"):  # Python bound method — supports WeakMethod
            self._bound.append(_BoundSlot[*Types].from_method(cast(_BoundMethod[*Types], slot)))
        else:
            if slot not in self._plain:
                self._plain.append(slot)

    def disconnect(self, slot: Callable[[*Types], None]) -> None:
        """Disconnect a previously connected callable.
        Silently ignored if not connected."""
        if hasattr(slot, "__func__"):  # Python bound method
            kept: list[_BoundSlot[*Types]] = []
            for s in self._bound:
                if s.ref() is not None and s.matches(cast(_BoundMethod[*Types], slot)) is False:
                    kept.append(s)
            self._bound = kept
        else:
            try:
                self._plain.remove(slot)
            except ValueError:
                pass

    def disconnect_all(self) -> None:
        """Remove all connected slots."""
        self._bound.clear()
        self._plain.clear()

    def emit(self, *payload: *Types) -> None:
        """
        Emit the signal synchronously. All connected slots are called in
        connection order. Dead weak references are pruned during this pass.
        """
        self._bound = [s for s in self._bound if s.call(*payload)]
        for slot in list(self._plain):
            slot(*payload)

    @property
    def receiver_count(self) -> int:
        """Number of live connected slots. Dead weak refs are not counted."""
        live_bound = sum(1 for s in self._bound if s.ref() is not None)
        return live_bound + len(self._plain)


class QSignal[*Types]:
    """
    Descriptor for declaring typed signals as class attributes.

    Creates a per-instance QSignalInstance on first access, so each instance
    gets its own independent signal — matching the behaviour you'd expect from Qt.

    Pass qt_signal=True on a QObject subclass to register a real Qt signal
    through PySide6's meta-object system instead::

        class Model(QObject):
            value_changed = QSignal[int](int, qt_signal=True)

    Without qt_signal=True (pure Python)::

        class Watcher:
            changed = QSignal[str]()
            error   = QSignal[Exception]()

        w1 = Watcher()
        w2 = Watcher()
        # w1.changed and w2.changed are separate QSignalInstance objects
    """

    @overload
    def __new__(cls, *types: type, qt: Literal[True]) -> Signal: ...
    @overload
    def __new__(cls, *types: type, qt: Literal[False]) -> QSignal[*Types]: ...
    @overload
    def __new__(cls, *types: type) -> QSignal[*Types]: ...
    
    def __new__(cls, *types: type, qt: bool = False) -> QSignal[*Types] | Signal:
        if qt:
            from PySide6.QtCore import Signal as _Signal
            return _Signal(*types)
        return super().__new__(cls)

    def __set_name__(self, owner: type, name: str) -> None:
        self._attr = f"__signal_{name}__"

    @overload
    def __get__(self, obj: None, objtype: type) -> QSignal[*Types]: ...
    @overload
    def __get__(self, obj: object, objtype: type) -> QSignalInstance[*Types]: ...

    def __get__(
        self,
        obj: object | None,
        objtype: type | None = None,
    ) -> QSignalInstance[*Types] | QSignal[*Types]:
        if obj is None:
            return self
        existing: QSignalInstance[*Types] | None = obj.__dict__.get(self._attr)
        if existing is None:
            existing = QSignalInstance[*Types]()
            obj.__dict__[self._attr] = existing
        return existing
