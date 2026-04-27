"""Factory for checkbox form field widgets."""

from PySide6.QtWidgets import QCheckBox, QWidget

from ....models import FormFieldSpec
from ..binding_model import FieldWidgetBinding


def build_checkbox_widget(spec: FormFieldSpec, parent: QWidget) -> FieldWidgetBinding:
    widget_box: QCheckBox = QCheckBox(parent)

    binding = FieldWidgetBinding(
        spec=spec,
        widget=widget_box,
        get_value=widget_box.isChecked,
        set_value=lambda v: widget_box.setChecked(bool(v))  
    )

    return binding
