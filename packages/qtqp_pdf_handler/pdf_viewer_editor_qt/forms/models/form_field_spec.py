"""Model for a single form field specification."""

from dataclasses import dataclass, field

from .field_flags import FieldFlags
from .field_kind import FieldKind


@dataclass(frozen=True, slots=True)
class FormFieldSpec:
    """Declarative description of a single PDF form field."""

    name: str
    label: str
    kind: FieldKind
    default_value: str | bool
    choices: list[str] = field(default_factory=list[str])
    flags: FieldFlags = field(default_factory=FieldFlags)
