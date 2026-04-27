"""Factory for combo box form field widgets."""

from PySide6.QtWidgets import QComboBox, QWidget

from ....models import FormFieldSpec
from ..binding_model import FieldWidgetBinding


def build_choice_widget(spec: FormFieldSpec, parent: QWidget) -> FieldWidgetBinding:
    widget_combo: QComboBox = QComboBox(parent)

    choices: list[str] = spec.choices
    if choices:
        widget_combo.addItems(choices)
        widget_combo.setEditable(False)
    else:
        widget_combo.setEditable(True)

    binding = FieldWidgetBinding(
        spec=spec,
        widget=widget_combo,
        get_value=widget_combo.currentText,
        set_value=lambda v: widget_combo.setCurrentText(str(v) if v else "")
    )

    return binding
