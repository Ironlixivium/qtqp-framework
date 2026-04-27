"""Flags describing form field behavior."""

from dataclasses import dataclass


@dataclass(slots=True)
class FieldFlags:
    """Behavioral flags for a form field."""

    read_only: bool = False
    required: bool = False
    multiline: bool = False