"""
PDF form field extraction.

PDF bytes <> list of form fields, via PyPdf.
"""


from collections.abc import Iterable
from enum import IntFlag
from io import BytesIO
from typing import cast

from pypdf import PdfReader
from pypdf.constants import FieldFlag
from pypdf.generic import Field, PdfObject

from ...models import FieldFlags, FieldKind, FormFieldSpec, FormSchema

_KIND_MAP: dict[str, FieldKind] = {
    "/Tx": FieldKind.TEXT,
    "/Ch": FieldKind.CHOICE,
    "/Sig": FieldKind.SIGNATURE,
}

class _ButtonFlag(IntFlag):
    RADIO = 1 << 15 # 32768
    PUSH = 1 << 16 # 65536


class PyPDFFieldExtractor:
    """AcroForm field extractor powered by pypdf."""

    def extract(self, pdf_bytes: bytes) -> FormSchema:
        """Extract AcroForm fields from PDF bytes and map them to a FormSchema."""
        reader = PdfReader(BytesIO(pdf_bytes))

        raw_fields = cast(dict[str, Field], reader.get_fields() or {})
        field_specs: list[FormFieldSpec] = []

        for field_name, field_dict in raw_fields.items():
            name = str(field_name)
            label = str(field_dict.get("/TU", name))
            kind = self._map_kind(field_dict)
            default_value = self._map_default_value(field_dict.get("/V", ""), kind)
            choices = self._map_choices(field_dict.get("/Opt", 0), kind)
            flags = self._map_flags(int(field_dict.get("/Ff", 0)), kind)

            field_specs.append(
                FormFieldSpec(
                    name=name,
                    label=label,
                    kind=kind,
                    default_value=default_value,
                    choices=choices,
                    flags=flags,
                )
            )

        return FormSchema(fields=field_specs)

    def _map_kind(self, field_dict: Field) -> FieldKind:
        """Map the PDF field type and flags to the internal FieldKind."""
        field_type = str(field_dict.get("/FT", ""))

        if field_type in _KIND_MAP:
            return _KIND_MAP[field_type]

        if field_type == "/Btn":
            ff_int: int = int(field_dict.get("/Ff", 0))
            
            if (ff_int & _ButtonFlag.PUSH) != 0:
                return FieldKind.UNKNOWN
            
            if (ff_int & _ButtonFlag.RADIO) != 0:
                return FieldKind.RADIO
            
            return FieldKind.CHECKBOX

        return FieldKind.UNKNOWN

    def _map_flags(self, ff_int: int, kind: FieldKind) -> FieldFlags:
        """Translate raw PDF flag bits into FieldFlags for the given kind."""
        flags = FieldFlags()
        basic_flags = FieldFlag(ff_int)
        flags.read_only = bool(basic_flags & FieldFlag.READ_ONLY)
        flags.required = bool(basic_flags & FieldFlag.REQUIRED)

        if kind is FieldKind.TEXT:
            flags.multiline = (ff_int & 1 << 12) != 0 # 4096 is multiline flag

        return flags

    def _map_default_value(self, value_obj: PdfObject, kind: FieldKind) -> str | bool:
        """Convert the PDF default value into a Python value for the field."""
        value_str = str(value_obj)

        if kind is FieldKind.CHECKBOX:
            v: str = value_str
            return v != "/Off"

        return value_str

    def _map_choices(self, opt_obj: PdfObject, kind: FieldKind) -> list[str]:
        """Extract choice values from the /Opt entry for choice or radio fields."""
        if kind not in (FieldKind.CHOICE, FieldKind.RADIO):
            return []

        try:
            options = list(cast(Iterable[PdfObject], opt_obj))
        except TypeError:
            return []
        
        values: list[str] = []
        for opt in options:
            try:
                opt_tup = tuple(cast(tuple[str], opt))
                values.append(str(opt_tup[1]))
                continue
            except TypeError:
                pass

            values.append(str(opt))

        return values
