"""Factory for text input form field widgets."""

from PySide6.QtWidgets import QLineEdit, QTextEdit, QWidget

from ....models import FormFieldSpec
from ..binding_model import FieldWidgetBinding


def build_text_widget(spec: FormFieldSpec, parent: QWidget) -> FieldWidgetBinding:
    if spec.flags.multiline:
        widget_text: QTextEdit = QTextEdit(parent)
        widget_text.setAcceptRichText(False)

        binding = FieldWidgetBinding(
            spec=spec,
            widget=widget_text,
            get_value=widget_text.toPlainText,
            set_value=lambda v: widget_text.setPlainText(str(v) if v else "")
        )
        
    else:
        widget_line: QLineEdit = QLineEdit(parent)

        binding = FieldWidgetBinding(
            spec=spec,
            widget=widget_line,
            get_value=widget_line.text,
            set_value=lambda v: widget_line.setText(str(v) if v else "")
        )

    return binding
