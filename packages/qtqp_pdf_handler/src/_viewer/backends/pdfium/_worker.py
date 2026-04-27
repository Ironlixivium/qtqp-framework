"""PDFium worker subprocess entry point.

Runs in a dedicated subprocess.  No Qt — only stdlib + pypdfium2.

Each worker maintains its own LRU cache of open PdfDocument objects so that
repeated renders of the same document do not re-parse the PDF bytes.
"""

from __future__ import annotations

import logging
from collections import OrderedDict
from multiprocessing.queues import Queue as MPQueue

import pypdfium2 as pdfium

from .._messages import (
    DescribeError,
    DescribeRequest,
    DescribeSuccess,
    RenderError,
    RenderRequest,
    RenderSuccess,
    ResultType,
    ShutdownConfirm,
    ShutdownRequest,
    new_result,
)

logger = logging.getLogger(__name__)

_MAX_OPEN_DOCS = 8


# ---------------------------------------------------------------------------
# Internal document cache (per-process)
# ---------------------------------------------------------------------------

def _get_or_open(
    cache: OrderedDict[str, pdfium.PdfDocument],
    doc_uid: str,
    doc_ref: bytes,
) -> pdfium.PdfDocument:
    doc = cache.get(doc_uid)
    if doc is not None:
        cache.move_to_end(doc_uid)
        return doc
    doc = pdfium.PdfDocument(doc_ref)
    cache[doc_uid] = doc
    cache.move_to_end(doc_uid)
    while len(cache) > _MAX_OPEN_DOCS:
        _, evicted = cache.popitem(last=False)
        try:
            evicted.close()
        except Exception:
            pass
    return doc


def _close_all(cache: OrderedDict[str, pdfium.PdfDocument]) -> None:
    for doc in cache.values():
        try:
            doc.close()
        except Exception:
            pass
    cache.clear()


# ---------------------------------------------------------------------------
# Job handlers
# ---------------------------------------------------------------------------

def _handle_render(
    job: RenderRequest,
    cache: OrderedDict[str, pdfium.PdfDocument],
) -> RenderSuccess | RenderError:
    page = None
    bitmap = None
    try:
        doc = _get_or_open(cache, job.doc_uid, job.doc_bytes)
        page = doc[job.page_index]
        bitmap = page.render(
            scale=job.target_dpi / 72.0,
            rotation=job.rotation_deg,
            fill_color=job.fill_color,
            draw_annots=job.draw_markups,
            may_draw_forms=job.may_draw_forms,
        )
        arr = bitmap.to_numpy()
        h = int(arr.shape[0])
        w = int(arr.shape[1])
        c = int(arr.shape[2]) if arr.ndim == 3 else 0
        fmt = "RGBA" if c == 4 else "RGB"
        return new_result(
            ResultType.RENDER_SUCCESS,
            job.doc_uid,
            job.request_id,
            page_index=job.page_index,
            image=bytes(arr.data),
            width=w,
            height=h,
            stride=int(arr.strides[0]),
            image_format=fmt,
            device_pixel_ratio=job.device_pixel_ratio,
        )
    except Exception as exc:
        return new_result(
            ResultType.RENDER_FAILURE,
            job.doc_uid,
            job.request_id,
            page_index=job.page_index,
            text=str(exc) or type(exc).__name__,
        )
    finally:
        try:
            if bitmap is not None:
                bitmap.close()
        except Exception:
            pass
        try:
            if page is not None:
                page.close()
        except Exception:
            pass


def _handle_describe(
    job: DescribeRequest,
    cache: OrderedDict[str, pdfium.PdfDocument],
) -> DescribeSuccess | DescribeError:
    try:
        doc = _get_or_open(cache, job.doc_uid, job.doc_bytes)
        page_sizes: list[tuple[float, float]] = []
        for i in range(len(doc)):
            w, h = doc.get_page_size(i)
            page_sizes.append((float(w), float(h)))
        return new_result(
            ResultType.DESCRIBE_SUCCESS,
            job.doc_uid,
            job.request_id,
            page_sizes_pt=page_sizes,
        )
    except Exception as exc:
        return new_result(
            ResultType.DESCRIBE_FAILURE,
            job.doc_uid,
            job.request_id,
            text=str(exc) or type(exc).__name__,
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def worker_main(
    request_q: MPQueue[RenderRequest | DescribeRequest | ShutdownRequest],
    result_q: MPQueue[RenderSuccess | RenderError | DescribeSuccess | DescribeError | ShutdownConfirm],
) -> None:
    """Main loop for a pdfium worker subprocess.  Exits on shutdown sentinel."""
    cache: OrderedDict[str, pdfium.PdfDocument] = OrderedDict()
    while True:
        job = request_q.get()
        if isinstance(job, ShutdownRequest):
            result_q.put(new_result(ResultType.SHUTDOWN_CONFIRM, "", ""))
            break
        if isinstance(job, RenderRequest):
            result_q.put(_handle_render(job, cache))
        else:
            result_q.put(_handle_describe(job, cache))
    _close_all(cache)
