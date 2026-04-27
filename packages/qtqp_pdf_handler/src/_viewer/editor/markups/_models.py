"""Annotation data models and serialization helpers."""
import logging
from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from typing import Any, Literal, Self, cast

from ...._color import Color
from ..geometry import PtRect
from ._typing import Markup, MarkupDict, MarkupKind, RectMarkupDict, StampMarkupDict, TextBoxMarkupDict

logger = logging.getLogger(__name__)

_BLACK = Color(red=0, green=0, blue=0, alpha=255)
_TRANSPARENT = Color(red=0, green=0, blue=0, alpha=0)

def _parse_field[T](
    source_dict: Mapping[str, Any],
    field: str,
    converter: Callable[[Any], T],
    default: T,
    errors: type[Exception] | tuple[type[Exception], ...] = Exception,
    *,
    context: str,
) -> T:
    """Read and convert a dict field with a fallback value.

    Logs warnings for missing/invalid values and returns ``default`` in those
    cases.
    """
    if field in source_dict:
        try:
            return converter(source_dict[field])
        except errors as e:
            logger.warning(
                "%s: invalid '%s' value %r, using default %r: %s",
                context, field, source_dict[field], default, e,
            )
            return default
    else:
        logger.warning("%s: missing '%s', using default %r", context, field, default)
        return default



@dataclass(frozen=True, slots=True)
class _MarkupBase[K: MarkupKind, D: MarkupDict](ABC):
    """Common frozen base class for markup models.

    Attributes
    ----------
    id:
        Stable identifier for the markup.
    page_index:
        Zero-based page index.
    rect:
        Rectangle in page-local point coordinates.
    kind:
        Markup kind discriminator.
    """

    id: str
    page_index: int
    rect: PtRect
    _kind: K

    @property
    def kind(self) -> K:
        return self._kind

    @classmethod
    @abstractmethod
    def from_dict(cls, markup_dict: Any) -> Self:
        """Parse a serialized markup dict into a model instance."""
        raise NotImplementedError

    @abstractmethod
    def to_dict(self) -> D:
        """Serialize this markup to a TypedDict."""
        raise NotImplementedError

    @staticmethod
    def _fields_from_dict(markup_dict: MarkupDict) -> tuple[str, int, PtRect]:
        """Parse common fields present on all markup dicts."""
        id=str(markup_dict.get("id", ""))
        page_index=int(markup_dict["page_index"])
        rect=PtRect.from_list(markup_dict["rect"])
        return id, page_index, rect

    def replace_rect(self, rect: PtRect) -> Self:
        """Return a copy with an updated rectangle."""
        return replace(self, rect=rect)

    def _fields_to_dict(self) -> D:
        """Serialize common fields for all markup dicts."""
        return cast(D, {
            "id": self.id,
            "page_index": self.page_index,
            "rect": self.rect.to_list(),
            "kind": self.kind.value,
        })

@dataclass(frozen=True, slots=True)
class RectMarkup(_MarkupBase[Literal[MarkupKind.RECT], RectMarkupDict]):
    """Rectangle markup with stroke + fill styling."""

    _kind: Literal[MarkupKind.RECT] = field(default=MarkupKind.RECT, init=False)
    stroke_color: Color
    stroke_width: float
    fill_color: Color

    @classmethod
    def from_dict(cls, markup_dict: RectMarkupDict) -> Self:
        """Parse a serialized rect markup dict."""
        id, page_index, rect = super()._fields_from_dict(markup_dict)
        return cls(
            id=id, page_index=page_index, rect=rect,
            stroke_color=_parse_field(markup_dict, "stroke_color", Color.from_rgba, _BLACK,
                                      context="RectMarkup.from_dict: RGBA border color"),
            stroke_width=_parse_field(markup_dict, "stroke_width", float, 1.0, (ValueError, TypeError),
                                      context="RectMarkup.from_dict: border width in points"),
            fill_color=_parse_field(markup_dict, "fill_color", Color.from_rgba, _TRANSPARENT,
                                    context="RectMarkup.from_dict: RGBA fill color"),
        )

    def to_dict(self) -> RectMarkupDict:
        """Serialize this rect markup."""
        result = super()._fields_to_dict()
        result["stroke_color"] = [*self.stroke_color.rgba]
        result["stroke_width"] = self.stroke_width
        result["fill_color"] = [*self.fill_color.rgba]
        return result


@dataclass(frozen=True, slots=True)
class TextBoxMarkup(_MarkupBase[MarkupKind.TEXT_BOX, TextBoxMarkupDict]):
    """Text box markup with font and padding styling."""

    _kind: Literal[MarkupKind.TEXT_BOX] = field(default=MarkupKind.TEXT_BOX, init=False)
    text: str
    font_size: float
    text_color: Color
    padding: float

    @classmethod
    def from_dict(cls, markup_dict: TextBoxMarkupDict) -> Self:
        """Parse a serialized text box markup dict."""
        id, page_index, rect = super()._fields_from_dict(markup_dict)
        return cls(
            id=id, page_index=page_index, rect=rect,
            text=_parse_field(markup_dict, "text", str, "",
                              context="TextBoxMarkup.from_dict: text content of the box"),
            font_size=_parse_field(markup_dict, "font_size", float, 12.0, (ValueError, TypeError),
                                   context="TextBoxMarkup.from_dict: font size in points"),
            text_color=_parse_field(markup_dict, "text_color", Color.from_rgba, _BLACK,
                                    context="TextBoxMarkup.from_dict: RGBA text color"),
            padding=_parse_field(markup_dict, "padding", float, 4.0, (ValueError, TypeError),
                                 context="TextBoxMarkup.from_dict: inner padding in points"),
        )

    def to_dict(self) -> TextBoxMarkupDict:
        """Serialize this text box markup."""
        result = super()._fields_to_dict()
        result["text"] = str(self.text)
        result["font_size"] = float(self.font_size)
        result["text_color"] = [*self.text_color.rgba]
        result["padding"] = float(self.padding)
        return result


@dataclass(frozen=True, slots=True)
class StampMarkup(_MarkupBase[MarkupKind.STAMP, StampMarkupDict]):
    """Stamp markup referencing an image asset ID."""

    _kind: Literal[MarkupKind.STAMP] = field(default=MarkupKind.STAMP, init=False)
    stamp_asset_id: str
    opacity: float

    @classmethod
    def from_dict(cls, markup_dict: StampMarkupDict) -> Self:
        """Parse a serialized stamp markup dict."""
        id, page_index, rect = super()._fields_from_dict(markup_dict)
        return cls(
            id=id, page_index=page_index, rect=rect,
            stamp_asset_id=_parse_field(markup_dict, "stamp_asset_id", str, "",
                                        context="StampMarkup.from_dict: ID referencing the stamp image asset"),
            opacity=_parse_field(markup_dict, "opacity", float, 1.0, (ValueError, TypeError),
                                 context="StampMarkup.from_dict: opacity in range 0.0-1.0"),
        )

    def to_dict(self) -> StampMarkupDict:
        """Serialize this stamp markup."""
        result = super()._fields_to_dict()
        result["stamp_asset_id"] = str(self.stamp_asset_id)
        result["opacity"] = float(self.opacity)
        return result

def create_markup_from_dict(markup_dict: MarkupDict) -> Markup:
    """Create a markup model instance from a serialized dict."""
    kind = markup_dict["kind"]
    match kind:
        case "rect":
            return RectMarkup.from_dict(cast(RectMarkupDict, markup_dict))
        case "stamp":
            return StampMarkup.from_dict(cast(StampMarkupDict, markup_dict))
        case "text_box":
            return TextBoxMarkup.from_dict(cast(TextBoxMarkupDict, markup_dict))
    return cast(Markup, None)
