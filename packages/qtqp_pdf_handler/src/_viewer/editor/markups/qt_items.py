"""Qt graphics item wrappers for rendering and editing annotations."""


from collections.abc import Callable
from dataclasses import replace
from typing import cast, overload

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QFocusEvent, QFont, QPen, QTransform
from PySide6.QtWidgets import QGraphicsItem, QGraphicsPixmapItem, QGraphicsRectItem, QGraphicsTextItem

from ..geometry import PtRect
from ..stamp_assets import StampRegistry
from ._models import RectMarkup, StampMarkup, TextBoxMarkup
from ._typing import Markup, MarkupItem, MarkupKind


class _MarkupItemBase[M: Markup](QGraphicsRectItem):
    """QGraphicsRectItem base that handles markup id, rect geometry, and read_back."""

    def __init__(self, markup: M) -> None:
        """Create a rect-based item and store the markup id."""
        super().__init__()
        self.id = markup.id

    def _apply_rect(self, markup: M) -> None:
        """Apply the markup rectangle to this item."""
        self.setRect(*markup.rect)

    def read_back(self, markup: M) -> M:
        """Read the current geometry back into a new markup instance."""
        r = self.rect()
        return markup.replace_rect(PtRect(r.x(), r.y(), r.width(), r.height()))

    def apply_markup(self, markup: M, *, stamps: StampRegistry | None = None, is_interactive: bool = False) -> None:
        """Apply styling/content based on the markup model."""
        raise NotImplementedError


class RectItem(_MarkupItemBase[RectMarkup]):
    """QGraphics item that renders a rectangle markup."""

    def __init__(self, markup: RectMarkup) -> None:
        """Create a rect item initialized from ``markup``."""
        super().__init__(markup)
        self.apply_markup(markup)

    def apply_markup(
        self,
        markup: RectMarkup,
        *,
        stamps: StampRegistry | None = None,
        is_interactive: bool = False,
    ) -> None:
        """Apply the markup's styling and geometry."""
        self._apply_rect(markup)
        pen = QPen(markup.stroke_color.q_color)
        pen.setWidthF(markup.stroke_width)
        self.setPen(pen)
        if markup.fill_color.alpha == 0:
            self.setBrush(Qt.BrushStyle.NoBrush)
        else:
            self.setBrush(QBrush(markup.fill_color.q_color))


class EditableTextItem(QGraphicsTextItem):
    """Text item that commits edits on focus loss."""

    def __init__(self, on_commit: Callable[[str], None], parent: QGraphicsItem | None = None) -> None:
        """Create a text item that calls ``on_commit`` when editing finishes."""
        super().__init__(parent=parent)
        self._on_commit = on_commit

    def focusOutEvent(self, event: QFocusEvent) -> None:
        """Commit edits when the item loses focus."""
        self._on_commit(self.toPlainText())
        super().focusOutEvent(event)


class TextBoxItem(_MarkupItemBase[TextBoxMarkup]):
    """QGraphics item that renders an editable text box markup."""

    def __init__(self, markup: TextBoxMarkup, *, on_commit_text: Callable[[str], None]) -> None:
        """Create a text box item with an embedded editable text widget."""
        super().__init__(markup)
        self.text_item = EditableTextItem(on_commit_text, self)
        self.text_item.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.apply_markup(markup)

    def enter_edit_mode(self) -> None:
        """Enable inline text editing."""
        self.text_item.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        self.text_item.setFocus(Qt.FocusReason.MouseFocusReason)

    def exit_edit_mode(self) -> None:
        """Disable inline text editing."""
        self.text_item.clearFocus()
        self.text_item.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)

    def apply_markup(
        self,
        markup: TextBoxMarkup,
        *,
        stamps: StampRegistry | None = None,
        is_interactive: bool = False,
    ) -> None:
        """Apply styling/text content and geometry from the markup."""
        self._apply_rect(markup)
        pen = QPen(markup.text_color.q_color)
        pen.setWidthF(1.0)
        self.setPen(pen)
        self.setBrush(Qt.BrushStyle.NoBrush)
        font = QFont()
        font.setPointSizeF(float(markup.font_size))
        self.text_item.setFont(font)
        self.text_item.setPlainText(markup.text)
        self.text_item.setPos(markup.rect.x + markup.padding, markup.rect.y + markup.padding)

    def read_back(self, markup: TextBoxMarkup) -> TextBoxMarkup:
        """Read the current geometry and text back into a new markup instance."""
        result = super().read_back(markup)
        return replace(result, text=self.text_item.toPlainText())


class StampItem(_MarkupItemBase[StampMarkup]):
    """QGraphics item that renders a stamp pixmap inside a rect."""

    def __init__(self, markup: StampMarkup, *, stamps: StampRegistry) -> None:
        """Create a stamp item initialized from ``markup``."""
        super().__init__(markup)
        self.pixmap_item = QGraphicsPixmapItem(self)
        self._current_asset_id: str | None = None
        self._current_is_preview = False
        self._base_pixmap_w = 0
        self._base_pixmap_h = 0
        self.apply_markup(markup, stamps=stamps)

    def _ensure_content(self, stamp_asset_id: str, stamps: StampRegistry, is_preview: bool) -> None:
        """Load and set the correct pixmap when the asset/preview changes."""
        if stamp_asset_id == self._current_asset_id and is_preview == self._current_is_preview:
            return
        pix = stamps.get_pixmap(stamp_asset_id, preview=is_preview)
        self.pixmap_item.setPixmap(pix)
        self._base_pixmap_w = pix.width()
        self._base_pixmap_h = pix.height()
        self._current_asset_id = stamp_asset_id
        self._current_is_preview = is_preview

    def _apply_geometry(self, rect: PtRect) -> None:
        """Scale and position the stamp pixmap to fit ``rect``."""
        self.pixmap_item.setPos(rect.x, rect.y)
        if self._base_pixmap_w > 0 and self._base_pixmap_h > 0:
            sx = rect.w / self._base_pixmap_w
            sy = rect.h / self._base_pixmap_h
            self.pixmap_item.setTransform(QTransform().scale(sx, sy))
        else:
            self.pixmap_item.setTransform(QTransform())

    def apply_markup(
        self,
        markup: StampMarkup,
        *,
        stamps: StampRegistry | None = None,
        is_interactive: bool = False,
    ) -> None:
        """Apply stamp pixmap, geometry, and opacity from the markup."""
        if stamps is None:
            return
        self._ensure_content(markup.stamp_asset_id, stamps, is_preview=is_interactive)
        self._apply_rect(markup)
        self.setPen(Qt.PenStyle.NoPen)
        self.setBrush(Qt.BrushStyle.NoBrush)
        self._apply_geometry(markup.rect)
        self.setOpacity(float(markup.opacity))

    # read_back inherited from BaseMarkupItem[StampMarkup]

@overload
def create_item(
    markup: RectMarkup, *, on_commit_text: Callable[[str], None] = ..., stamps: StampRegistry
) -> RectItem:
    """Overload: create a ``RectItem``."""
    ...
@overload
def create_item(
    markup: StampMarkup, *, on_commit_text: Callable[[str], None] = ..., stamps: StampRegistry
) -> StampItem:
    """Overload: create a ``StampItem``."""
    ...
@overload
def create_item(
    markup: TextBoxMarkup, *, on_commit_text: Callable[[str], None] = ..., stamps: StampRegistry
) -> TextBoxItem:
    """Overload: create a ``TextBoxItem``."""
    ...
@overload
def create_item(
    markup: Markup, *, on_commit_text: Callable[[str], None] = ..., stamps: StampRegistry
) -> MarkupItem:
    """Overload: create a generic ``MarkupItem``."""
    ...
def create_item(
    markup: Markup,
    *,
    on_commit_text: Callable[[str], None] = lambda t: None,
    stamps: StampRegistry,
) -> MarkupItem:
    """Create the appropriate Qt item for a given markup model."""
    kind = markup.kind
    match kind:
        case MarkupKind.RECT:
            return RectItem(cast(RectMarkup, markup))
        case MarkupKind.STAMP:
            return StampItem(cast(StampMarkup, markup), stamps=stamps)
        case MarkupKind.TEXT_BOX:
            return TextBoxItem(cast(TextBoxMarkup, markup), on_commit_text=on_commit_text)
    return cast(MarkupItem, None)
