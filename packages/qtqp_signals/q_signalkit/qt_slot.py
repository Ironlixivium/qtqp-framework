"""
Optional PySide6 utilities.

Import this module only in projects that use PySide6. The core signalkit
package does not import PySide6 by default.

QSignal / SignalDescriptor are for pure-Python objects. On a QObject, use
PySide6's Signal() directly — it's the only way to satisfy the meta-object
system (cross-thread connections, QML, introspection).

The one thing this module provides on top of PySide6 is QSlot: a drop-in
for @Slot that infers argument and return types from annotations automatically.
"""
import inspect
import types
import typing
from collections.abc import Callable
from typing import Any, get_type_hints

from PySide6.QtCore import Slot as _Slot

__all__ = ["QSlot"]


def _unwrap_slot_type(t: Any) -> Any | None:
    """
    Reduce a type hint to a form PySide6's Slot accepts.

    Returns None when the type represents 'no value' (NoneType / -> None),
    signalling that the caller should omit the ``result`` keyword entirely.
    """
    # -> None  →  omit result=
    if t is type(None):
        return None

    # NewType wrappers  →  recurse into the supertype
    supertype = getattr(t, "__supertype__", None)
    if supertype is not None:
        return _unwrap_slot_type(supertype)

    # Optional[X] / Union[X, None] / X | None  →  unwrap to X
    # Real multi-type unions degrade to object (Qt can't express them)
    origin = getattr(t, "__origin__", None)
    is_union = origin is typing.Union or (
        isinstance(origin, type) is False and origin is types.UnionType
    )
    if is_union:
        non_none = [a for a in t.__args__ if a is not type(None)]
        if len(non_none) == 1:
            return _unwrap_slot_type(non_none[0])
        return object

    # Generic aliases like list[int], dict[str, int]  →  bare origin type
    if origin is not None:
        return origin

    return t


def QSlot(func: Callable[..., Any], /) -> Callable[..., Any]:
    """
    Decorator that registers a method as a Qt slot, inferring argument
    and return types from its annotations. Replaces PySide6's @Slot.

    Type aliases, Optional, generics, and NewType are unwrapped to the
    nearest Qt-compatible base type automatically.

    Usage::

        class MyWidget(QWidget):
            @QSlot
            def on_value_changed(self, value: int) -> None: ...
    """
    hints = get_type_hints(func)
    params = list(inspect.signature(func).parameters.keys())

    if params and params[0] == "self":
        params = params[1:]

    arg_types = [_unwrap_slot_type(hints[p]) for p in params if p in hints]
    # Filter out any None entries (unannotated or NoneType params — rare but safe)
    arg_types = [t for t in arg_types if t is not None]

    raw_return = hints.get("return")
    result_type = _unwrap_slot_type(raw_return) if raw_return is not None else None

    if result_type is not None:
        return _Slot(*arg_types, result=result_type)(func)
    return _Slot(*arg_types)(func)
