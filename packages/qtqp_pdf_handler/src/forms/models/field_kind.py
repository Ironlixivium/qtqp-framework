"""Enumeration of supported form field kinds."""

from enum import Enum, auto


class FieldKind(Enum):
    """Supported PDF form field kinds.

    Note:
        Not all PDFs expose form fields the same way. Unknown/unsupported fields
        should be mapped to UNKNOWN by extractors.
    """

    TEXT = auto()
    CHECKBOX = auto()
    RADIO = auto()
    CHOICE = auto()
    SIGNATURE = auto()
    UNKNOWN = auto()