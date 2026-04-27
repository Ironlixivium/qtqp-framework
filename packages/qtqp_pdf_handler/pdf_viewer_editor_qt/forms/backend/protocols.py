"""Protocols for form field extraction and filling."""

from typing import Protocol

from ..models import FormSchema, UserInputValues


class FieldExtractor(Protocol):
    """Extracts a FormSchema from PDF bytes."""

    def extract(self, pdf_bytes: bytes) -> FormSchema:
        """Return a schema describing editable fields in the PDF."""
        raise NotImplementedError

class FormFiller(Protocol):
    """Fills PDF form fields with values and returns new PDF bytes."""

    def fill(self, pdf_bytes: bytes, values: UserInputValues) -> bytes:
        """Return filled PDF bytes."""
        raise NotImplementedError
