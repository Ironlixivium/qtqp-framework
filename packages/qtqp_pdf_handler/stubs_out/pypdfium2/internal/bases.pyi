import enum
from _typeshed import Incomplete

__all__ = ["AutoCastable", "AutoCloseable", "DEBUG_AUTOCLOSE", "LIBRARY_AVAILABLE", "_safe_debug"]

def _safe_debug(msg) -> None: ...

class _Mutable:
    value: Incomplete
    def __init__(self, value) -> None: ...
    def __repr__(self) -> str: ...
    def __bool__(self) -> bool: ...

DEBUG_AUTOCLOSE: Incomplete
LIBRARY_AVAILABLE: Incomplete

class _STATE(enum.Enum):
    INVALID = -1
    AUTO = 0
    EXPLICIT = 1
    BYPARENT = 2

class AutoCastable:
    @property
    def _as_parameter_(self): ...

class AutoCloseable(AutoCastable):
    _close_func: Incomplete
    _obj: Incomplete
    _ex_args: Incomplete
    _ex_kwargs: Incomplete
    _autoclose_state: Incomplete
    _uuid: Incomplete
    _finalizer: Incomplete
    _kids: Incomplete
    def __init__(self, close_func, *args, obj=None, needs_free: bool = True, **kwargs) -> None: ...
    def __repr__(self) -> str: ...
    def _attach_finalizer(self) -> None: ...
    def _detach_finalizer(self) -> None: ...
    def _tree_closed(self): ...
    def _add_kid(self, k) -> None: ...
    raw: Incomplete
    def close(self, _by_parent: bool = False) -> None: ...
