"""Type definitions for markup serialization and Qt item interop."""

from enum import StrEnum
from typing import TYPE_CHECKING, Literal, Protocol, Self, TypedDict, cast, runtime_checkable

from PySide6.QtWidgets import QGraphicsItem, QGraphicsScene

from ..geometry import PtRect
from ..stamp_assets import StampRegistry


class MarkupKind(StrEnum):
    """Supported markup kinds (stable serialized values)."""

    RECT = "rect"
    STAMP = "stamp"
    TEXT_BOX = "text_box"

type KindLiteral = Literal[
    "rect",
    "stamp",
    "text_box",
]


class MarkupDictBaseFields[K: KindLiteral](TypedDict):
    """Fields common to all serialized markup dictionaries."""

    id: str
    page_index: int
    rect: list[float]
    kind: K

class RectMarkupDict(MarkupDictBaseFields[Literal["rect"]]):
    """Serialized rect markup."""

    stroke_color: list[int]
    stroke_width: float
    fill_color: list[int]

class StampMarkupDict(MarkupDictBaseFields[Literal["stamp"]]):
    """Serialized stamp markup."""

    stamp_asset_id: str
    opacity: float

class TextBoxMarkupDict(MarkupDictBaseFields[Literal["text_box"]]):
    """Serialized text box markup."""

    text: str
    text_color: list[int]
    font_size: float
    padding: float

type MarkupDict = RectMarkupDict | TextBoxMarkupDict | StampMarkupDict


if TYPE_CHECKING:
    def check_kind_enum_to_literal(ke: MarkupKind) -> KindLiteral:
        match ke:
            case MarkupKind.RECT:
                return MarkupKind.RECT.value
            case MarkupKind.STAMP:
                return MarkupKind.STAMP.value
            case MarkupKind.TEXT_BOX:
                return MarkupKind.TEXT_BOX.value

    def check_kind_literal_to_enum(kl: KindLiteral) -> MarkupKind:
        match kl:
            case "rect":
                return MarkupKind(kl)
            case "stamp":
                return MarkupKind(kl)
            case "text_box":
                return MarkupKind(kl)

    def check_dict_to_enum(md: MarkupDict) -> MarkupKind:
        kind = md["kind"]
        match kind:
            case "rect":
                return MarkupKind(kind)
            case "stamp":
                return MarkupKind(kind)
            case "text_box":
                return MarkupKind(kind)


class Markup(Protocol):
    """Common interface for markup models used by the editor."""

    @property
    def id(self) -> str:
        """Stable identifier for the markup."""
        ...
    @property
    def page_index(self) -> int:
        """Zero-based page index the markup belongs to."""
        ...
    @property
    def rect(self) -> PtRect:
        """Rectangle in page-local point coordinates."""
        ...
    @property
    def kind(self) -> MarkupKind:
        """Discriminator for the markup kind."""
        ...

    def replace_rect(self, rect: PtRect) -> Self:
        """Return a copy with an updated rectangle."""
        ...

    def to_dict(self) -> MarkupDict:
        """Serialize to a TypedDict representation."""
        ...

class _MarkupItem[M: Markup](Protocol):
    """Qt item adapter for a specific markup model type."""

    id: str
    def apply_markup(self, markup: M, *, stamps: StampRegistry | None = None, is_interactive: bool = False) -> None:
        """Apply a markup's data and styling to the item."""
        ...

    def read_back(self, markup: M) -> M:
        """Read the item's current state back into a markup instance."""
        ...

    def setParentItem(self, parent: QGraphicsItem) -> None:
        """Attach the item to a parent item."""
        ...

    def scene(self) -> QGraphicsScene:
        """Return the scene this item belongs to."""
        ...

@runtime_checkable
class MarkupItem(_MarkupItem[Markup], Protocol):
    """Runtime-checkable protocol for any editor markup item."""

if TYPE_CHECKING:
    from ._models import RectMarkup, StampMarkup, TextBoxMarkup
    _check_rect: Markup = cast(RectMarkup, None)
    _check_stamp: Markup = cast(StampMarkup, None)
    _check_text: Markup = cast(TextBoxMarkup, None)
