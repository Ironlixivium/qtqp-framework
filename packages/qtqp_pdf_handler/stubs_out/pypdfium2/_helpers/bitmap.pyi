import ctypes
from typing import Any

import pypdfium2.internal as pdfium_i
from _typeshed import Incomplete
from numpy import ndarray

__all__ = ["PdfBitmap", "PdfPosConv"]

class PdfBitmap(pdfium_i.AutoCloseable):
    raw: Incomplete
    buffer: Incomplete
    width: Incomplete
    height: Incomplete
    stride: Incomplete
    format: Incomplete
    rev_byteorder: Incomplete
    n_channels: Incomplete
    mode: Incomplete
    _pos_args: Incomplete
    def __init__(self, raw, buffer, width, height, stride, format, rev_byteorder, needs_free) -> None: ...
    @property
    def parent(self) -> None: ...
    @staticmethod
    def _get_buffer(raw, stride, height): ...
    @classmethod
    def from_raw(cls, raw, rev_byteorder: bool = False, ex_buffer=None): ...
    @classmethod
    def new_native(cls, 
        width: int,
        height: int,
        format: int,
        rev_byteorder: bool = False,
        buffer: ctypes.Array[Any] | bytes | bytearray | memoryview | None = None,
        stride: int | None = None,
    ) -> PdfBitmap: ...
    @classmethod
    def new_foreign(cls, width, height, format, rev_byteorder: bool = False, force_packed: bool = False): ...
    @classmethod
    def new_foreign_simple(cls, width, height, use_alpha, rev_byteorder: bool = False): ...
    def fill_rect(self, color, left, top, width, height) -> None: ...
    def to_numpy(self) -> Any: ...
    def to_pil(self): ...
    @classmethod
    def from_pil(cls, pil_image): ...
    def get_posconv(self, page): ...

class PdfPosConv:
    page: Incomplete
    pos_args: Incomplete
    def __init__(self, page, pos_args) -> None: ...
    def __repr__(self) -> str: ...
    def to_page(self, bitmap_x, bitmap_y): ...
    def to_bitmap(self, page_x, page_y): ...
