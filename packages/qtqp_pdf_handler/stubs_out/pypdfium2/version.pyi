from _typeshed import Incomplete

__all__ = ["PYPDFIUM_INFO", "PDFIUM_INFO"]

class _version_class:
    api_tag: Incomplete
    version: Incomplete
    def __init__(self) -> None: ...
    def __repr__(self) -> str: ...
    def _craft_tag(self): ...
    def _craft_desc(self, *suffixes): ...

class _version_pypdfium2(_version_class):
    _FILE: Incomplete
    _TAG_FIELDS: Incomplete
    tag: Incomplete
    desc: Incomplete
    def _hook(self) -> None: ...

class _version_pdfium(_version_class):
    _FILE: Incomplete
    _TAG_FIELDS: Incomplete
    flags: Incomplete
    tag: Incomplete
    desc: Incomplete
    def _hook(self) -> None: ...

PYPDFIUM_INFO: Incomplete
PDFIUM_INFO: Incomplete
