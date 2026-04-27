"""Binding model between form fields and Qt widgets."""

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtWidgets import QWidget

from ...models import FormFieldSpec


@dataclass(slots=True)
class FieldWidgetBinding:
    """A field spec bound to a Qt widget with get/set functions."""

    spec: FormFieldSpec
    widget: QWidget
    get_value: Callable[[], str | bool]
    set_value: Callable[[str | bool], None]

