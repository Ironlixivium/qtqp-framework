"""Form schema model for discovered PDF fields."""

from dataclasses import dataclass, field

from .form_field_spec import FormFieldSpec


@dataclass(frozen=True, slots=True)
class FormSchema:
    """A schema describing all fields discovered in a PDF document."""

    fields: list[FormFieldSpec] = field(default_factory=list[FormFieldSpec])

    def is_empty(self) -> bool:
        """Return True when no form fields were discovered."""
        return len(self.fields) == 0

    def get(self, name: str) -> FormFieldSpec | None:
        """Return the field spec matching `name`, or None if not present."""
        for field_spec in self.fields:
            if field_spec.name == name:
                return field_spec

        return None