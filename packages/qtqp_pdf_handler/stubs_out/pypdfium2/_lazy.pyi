import functools
from _typeshed import Incomplete

logger: Incomplete
cached_property = functools.cached_property

class _LazyClass:
    @cached_property
    def PIL_Image(self): ...
    @cached_property
    def numpy(self): ...

Lazy: Incomplete
