"""Backend coordination layer between a UI thread runner (Qt) and PDF backends.

Qt-free. Provides:
    - A small coordinator that runs extract/fill operations
    - Consistent error formatting
    - Cooperative cancellation by job_id (result suppression)

Does NOT:
    - Manage threads
    - Emit Qt signals
    - Show dialogs
"""

from dataclasses import dataclass
from typing import Literal

from ..models import FormSchema, UserInputValues
from .protocols import FieldExtractor, FormFiller
from .selector import Backend, get_backend

type _Operation = Literal["extract", "fill"]

@dataclass(frozen=True, slots=True)
class BackendResult:
    """Unified result for both extract and fill operations."""

    job_id: str
    op: _Operation
    ok: bool
    payload: bytes | FormSchema | None = None
    error: str | None = None

class PdfFormBackendCoordinator:
    """Runs extract/fill using injected services, with cooperative cancellation."""

    def __init__(self) -> None:
        self._extractor: FieldExtractor
        self._filler: FormFiller
        self._canceled_job_ids: set[str] = set()
        self._backend_connected: bool = False

        self.connect_backend("pypdf")

    def cancel(self, job_id: str) -> None:
        """Cancel a job (cooperative). Results for this job_id will be suppressed."""
        self._canceled_job_ids.add(job_id)

    def is_canceled(self, job_id: str) -> bool:
        """Return True if the given job_id has been canceled."""
        return job_id in self._canceled_job_ids

    def run(
            self,
            op: _Operation,
            *,
            job_id: str,
            pdf_bytes: bytes,
            values: UserInputValues | None = None
        ) -> BackendResult | None:
        if not self._backend_connected:
            raise Exception

        if self.is_canceled(job_id):
            return None

        try:
            if op == "fill":
                if values is None:
                    raise ValueError(values)
                result = self._filler.fill(pdf_bytes, values)

            elif op == "extract":
                result = self._extractor.extract(pdf_bytes)

            else:
                raise ValueError(op)

        except Exception as exc:
            if self.is_canceled(job_id):
                return None
            return BackendResult(
                job_id=job_id,
                op=op,
                ok=False,
                error=self._format_error(exc),
            )

        if self.is_canceled(job_id):
            return None
        
        return BackendResult(
            job_id=job_id,
            op=op,
            ok=True,
            payload=result,
        )

    def connect_backend(self, backend: Backend) -> None:
        extractor, filler = get_backend(backend)
        self._extractor = extractor
        self._filler = filler
        self._backend_connected = True

    def _format_error(self, exc: Exception) -> str:
        """Return a stable, user-displayable error message."""
        message: str = str(exc).strip()
        return message if message else exc.__class__.__name__