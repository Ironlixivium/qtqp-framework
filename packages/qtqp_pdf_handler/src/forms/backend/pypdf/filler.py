"""PDF form filling (Qt-free).

This module applies user-provided field values to a PDF (AcroForm) and returns
new PDF bytes suitable for loading into the existing viewer/editor.
"""

import logging
from collections.abc import Mapping
from io import BytesIO

from pypdf import PdfReader, PdfWriter

from ...models import UserInputValues

logger = logging.getLogger(__name__)

type PyPdfMapping = Mapping[str, str | list[str] | tuple[str, str, float]]

class PyPDFFormFiller:
    """AcroForm filler powered by pypdf."""

    def fill(self, pdf_bytes: bytes, values: UserInputValues) -> bytes:
        """Fill AcroForm fields in the given PDF bytes and return updated bytes."""
        reader = PdfReader(BytesIO(pdf_bytes))

        normalized_values = self._normalize_values(values)

        writer = PdfWriter()
        writer.clone_document_from_reader(reader)

        for page in writer.pages:
            writer.update_page_form_field_values(page, normalized_values, auto_regenerate=True)

        output = BytesIO()
        writer.write(output)
        return output.getvalue()

    def _normalize_values(self, values: UserInputValues) -> PyPdfMapping:
        """Normalize form values for pypdf, coercing booleans and nulls."""
        normalized: PyPdfMapping = {}
        for key, value in values.items():
            if isinstance(value, bool):
                normalized[key] = "/Yes" if value else "/Off"
            else:
                normalized[key] = "" if value is None else value
        return normalized