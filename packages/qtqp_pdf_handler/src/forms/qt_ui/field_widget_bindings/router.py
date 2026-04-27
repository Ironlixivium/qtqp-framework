"""Widget factory for PDF form fields (Qt-only).

This module maps FormFieldSpec -> QWidget bindings. It contains no PDF parsing
and no file I/O. It exists so PdfFormDialog stays focused on layout + validation.
"""

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from ...models import FieldKind, FormFieldSpec
from .binding_model import FieldWidgetBinding
from .factories import build_checkbox_widget, build_choice_widget, build_text_widget

type _FactoryFunc = Callable[[FormFieldSpec, QWidget], FieldWidgetBinding | None]
type _BindingFactoryMap = dict[FieldKind, _FactoryFunc]

def _ignore_field(_spec: FormFieldSpec, _parent: QWidget) -> None:
    return None

_factories: _BindingFactoryMap = {
    FieldKind.TEXT: build_text_widget,
    FieldKind.CHOICE: build_choice_widget,
    FieldKind.RADIO: build_choice_widget,
    FieldKind.CHECKBOX: build_checkbox_widget,
    FieldKind.SIGNATURE: _ignore_field
}

def build_field_widget_binding(spec: FormFieldSpec, *, parent: QWidget) -> FieldWidgetBinding | None:
    """Create a widget binding for the given field spec."""
    kind = spec.kind
    if kind not in _factories:
        return None

    binding = _factories[kind](spec, parent)

    if binding is None:
        return None

    # Apply defaults + read-only fields
    binding.set_value(spec.default_value)

    if spec.flags.read_only:
        binding.widget.setEnabled(False)

    # Reduce accidental scroll-stealing on checkboxes/combos inside scroll areas
    binding.widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    return binding


