"""Backend selection utilities for form processing."""

from typing import Literal

from .protocols import FieldExtractor, FormFiller

type Backend = Literal["pypdf"]

def get_backend(backend: Backend) -> tuple[FieldExtractor, FormFiller]:
    if backend == "pypdf":
        from .pypdf import PyPDFFieldExtractor, PyPDFFormFiller
        return (PyPDFFieldExtractor(), PyPDFFormFiller())
    else:
        raise Exception(f"unknown backend{backend}")