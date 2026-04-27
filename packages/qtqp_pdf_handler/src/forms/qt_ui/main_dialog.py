"""Dialog for filling PDF form fields (Qt-only).

Responsibilities:
    - Render a FormSchema into editable widgets (via widgets.build_field_widget)
    - Validate basic required fields
    - Return collected values as dict[name -> value]

Non-responsibilities:
    - PDF parsing / filling
    - File I/O
"""

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..models import FormFieldSpec, FormSchema, UserInputValues
from .field_widget_bindings import FieldWidgetBinding, build_field_widget_binding


class PdfFormDialog(QDialog):
    """Modal dialog that collects values for all fields in a FormSchema."""

    def __init__(
        self,
        schema: FormSchema,
        *,
        parent: QWidget | None = None,
        title: str = "Fill PDF Fields",
        group_by_prefix: bool = True,
    ) -> None:
        """Initialize the dialog with schema-backed widgets and options."""
        super().__init__(parent)

        self._schema: FormSchema = schema
        self._group_by_prefix: bool = group_by_prefix
        self._bindings: list[FieldWidgetBinding] = []

        self.setWindowTitle(title)
        self._build_ui()

    def values(self) -> UserInputValues:
        """Return collected field values keyed by PDF field name."""
        values_by_name: UserInputValues = {}
        for binding in self._bindings:
            values_by_name[binding.spec.name] = binding.get_value()
        return values_by_name

    def _build_ui(self) -> None:
        """Build the scrollable form UI, widgets, and dialog buttons."""
        root_layout: QVBoxLayout = QVBoxLayout(self)

        # Best practice: scrollable form content (forms can be huge)
        scroll_area: QScrollArea = QScrollArea(self)
        scroll_area.setWidgetResizable(True)

        content_widget: QWidget = QWidget(scroll_area)
        content_layout: QVBoxLayout = QVBoxLayout(content_widget)

        groups = self._group_fields(self._schema.fields)
        for group_title, field_specs in groups.items():
            group_box: QGroupBox = QGroupBox(group_title, content_widget)
            form_layout: QFormLayout = QFormLayout(group_box)

            for spec in field_specs:
                binding = build_field_widget_binding(spec, parent=group_box)
                if binding is None:
                    continue
                
                form_layout.addRow(spec.label, binding.widget)
                self._bindings.append(binding)

            group_box.setLayout(form_layout)
            content_layout.addWidget(group_box)

        content_layout.addStretch(1)
        scroll_area.setWidget(content_widget)
        root_layout.addWidget(scroll_area, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        root_layout.addWidget(buttons)

    def _on_accept(self) -> None:
        """Validate required fields before accepting the dialog."""
        if not self._validate_required_fields():
            return
        self.accept()

    def _validate_required_fields(self) -> bool:
        """Return True when all required fields are filled, showing errors otherwise."""
        for binding in self._bindings:
            spec: FormFieldSpec = binding.spec
            if not spec.flags.required:
                continue

            value = binding.get_value()

            if isinstance(value, bool):
                ok = value
            else:
                text = value.strip()
                ok = text != ""

            if ok:
                continue

            QMessageBox.warning(self, "Missing Required Field", f"Please fill: {spec.label}")
            binding.widget.setFocus()
            return False

        return True

    def _group_fields(self, fields: list[FormFieldSpec]) -> dict[str, list[FormFieldSpec]]:
        """Group fields by prefix when enabled, preserving original order."""
        # Best practice: optional grouping by prefix (e.g. "Name.*", "Address.*")
        if not self._group_by_prefix:
            return {"Fields": list(fields)}

        prefixes_in_order: list[str] = []
        prefix_set: set[str] = set()

        for spec in fields:
            prefix: str = spec.name.split(".", 1)[0] if "." in spec.name else "Fields"
            if prefix not in prefix_set:
                prefix_set.add(prefix)
                prefixes_in_order.append(prefix)

        if len(prefixes_in_order) <= 1:
            return {"Fields": list(fields)}

        grouped: dict[str, list[FormFieldSpec]] = {prefix: [] for prefix in prefixes_in_order}
        for spec in fields:
            prefix = spec.name.split(".", 1)[0] if "." in spec.name else "Fields"
            grouped[prefix].append(spec)

        return grouped