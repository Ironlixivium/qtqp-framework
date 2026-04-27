"""PDFium backend worker.

Exports the subprocess entry point used by BackendController.
"""

from ._worker import worker_main

__all__ = ["worker_main"]
