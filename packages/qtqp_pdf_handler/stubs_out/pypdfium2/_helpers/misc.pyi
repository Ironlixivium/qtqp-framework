from _typeshed import Incomplete

__all__ = ["PdfiumError"]

class PdfiumError(RuntimeError):
    err_code: Incomplete
    def __init__(self, msg, err_code=None) -> None: ...
