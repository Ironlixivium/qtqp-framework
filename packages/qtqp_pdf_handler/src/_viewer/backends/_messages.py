"""Picklable message types for process ↔ BackendController communication.

All types must be picklable so they can cross process boundaries via
multiprocessing.Queue.  No Qt types allowed here.
"""

import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal, TypedDict, Unpack, overload

# ---------------------------------------------------------------------------
# Jobs  (controller → worker)
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class _MessageBase:
    """
    This type must remain picklable (no Qt types) because it is passed through a
    ``multiprocessing.Queue``.
    """
    doc_uid: str
    request_id: str


@dataclass(frozen=True, slots=True)
class RenderRequest(_MessageBase):
    """Request to render a single page."""
    device_pixel_ratio: float
    doc_bytes: bytes
    draw_markups: bool
    fill_color: tuple[int, int, int, int]
    may_draw_forms: bool
    page_index: int
    rotation_deg: int
    target_dpi: float | None
    target_size_px: tuple[int, int] | None
    zoom: float


@dataclass(frozen=True, slots=True)
class DescribeRequest(_MessageBase):
    """Request to describe a document (page sizes, title, etc.)."""
    doc_bytes: bytes

@dataclass(frozen=True, slots=True)
class ShutdownRequest(_MessageBase):
    doc_uid: Literal[""] = field(default="", init=False)
    request_id: Literal[""] = field(default="", init=False)


# ---------------------------------------------------------------------------
# Results  (worker → controller)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RenderSuccess(_MessageBase):
    """Successful render response containing raw image bytes and metadata."""
    page_index: int
    image: bytes
    width: int
    height: int
    stride: int
    image_format: Literal["RGB", "RGBA"]
    device_pixel_ratio: float


@dataclass(frozen=True, slots=True)
class RenderError(_MessageBase):
    """Failed render response with a human-readable message."""
    page_index: int
    text: str


@dataclass(frozen=True, slots=True)
class DescribeSuccess(_MessageBase):
    """Successful describe response containing page sizes (in points)."""
    title: str
    page_sizes_pt: list[tuple[float, float]]


@dataclass(frozen=True, slots=True)
class DescribeError(_MessageBase):
    """Failed describe response with a human-readable message."""
    text: str


@dataclass(frozen=True, slots=True)
class ShutdownConfirm(_MessageBase):
    doc_uid: Literal[""] = field(default="", init=False)
    request_id: Literal[""] = field(default="", init=False)


class RequestType(StrEnum):
    DESCRIBE = "describe"
    RENDER = "render"
    SHUTDOWN = "shutdown"

def _new_uid(obj: object, *, identifier:str = "") -> str:
    return f"{identifier} + {uuid.uuid4().hex}"

def new_request(
        type: RequestType,
        doc_uid: str,
        doc_bytes: bytes,
        *,
        page_index: int | None = None,
        device_pixel_ratio: float = 1,
        draw_markups: bool = True,
        fill_color: tuple[int, int, int, int] = (255, 255, 255, 255),
        may_draw_forms: bool = True,
        rotation_deg: int = 0,
        target_dpi: float | None = None,
        target_size_px: tuple[int, int] | None = None,
        zoom: float = 1,


    ) -> DescribeRequest | RenderRequest | ShutdownRequest:
    match type:
        case RequestType.DESCRIBE:
            return DescribeRequest(
                doc_uid=doc_uid,
                doc_bytes=doc_bytes,
                request_id=_new_uid(doc_uid)
            )
        case RequestType.RENDER:
            if page_index is None:
                raise TypeError("Render requests must include a page number!")
            return RenderRequest(
                    device_pixel_ratio=device_pixel_ratio,
                    doc_bytes=doc_bytes,
                    doc_uid=doc_uid,
                    draw_markups=draw_markups,
                    fill_color=fill_color,
                    may_draw_forms=may_draw_forms,
                    page_index=page_index,
                    request_id=_new_uid(doc_uid),
                    rotation_deg=rotation_deg,
                    target_dpi=target_dpi,
                    target_size_px=target_size_px,
                    zoom=zoom,
                )
        case RequestType.SHUTDOWN:
            return ShutdownRequest()

class ResultType(StrEnum):
    DESCRIBE_FAILURE = "describe_failure"
    DESCRIBE_SUCCESS = "describe_success"
    RENDER_FAILURE = "render_failure"
    RENDER_SUCCESS = "render_success"
    SHUTDOWN_CONFIRM = "shutdown_confirm"

class _ResultKwargs(TypedDict, total=False):
    page_index:          int | None
    image:               bytes | None
    width:               int
    height:              int
    stride:              int
    image_format:        Literal["RGB", "RGBA"]
    device_pixel_ratio:  float
    title:               str
    page_sizes_pt:       list[tuple[float, float]] | None
    text:                str

@overload
def new_result(type: Literal[ResultType.RENDER_SUCCESS], doc_uid: str, request_id: str, **kwargs: Unpack[_ResultKwargs]) -> RenderSuccess: ...  # noqa: E501
@overload
def new_result(type: Literal[ResultType.RENDER_FAILURE], doc_uid: str, request_id: str, **kwargs: Unpack[_ResultKwargs]) -> RenderError: ...  # noqa: E501
@overload
def new_result(type: Literal[ResultType.DESCRIBE_SUCCESS], doc_uid: str, request_id: str, **kwargs: Unpack[_ResultKwargs]) -> DescribeSuccess: ...  # noqa: E501
@overload
def new_result(type: Literal[ResultType.DESCRIBE_FAILURE], doc_uid: str, request_id: str, **kwargs: Unpack[_ResultKwargs]) -> DescribeError: ...  # noqa: E501
@overload
def new_result(type: Literal[ResultType.SHUTDOWN_CONFIRM], doc_uid: str, request_id: str, **kwargs: Unpack[_ResultKwargs]) -> ShutdownConfirm: ...  # noqa: E501
def new_result(
        type: ResultType,
        doc_uid: str,
        request_id: str,
        *,
        page_index: int | None = None,
        image: bytes | None = None,
        width: int = 0,
        height: int = 0,
        stride: int = 0,
        image_format: Literal["RGB", "RGBA"] = "RGB",
        device_pixel_ratio: float = 1,
        title: str = "",
        page_sizes_pt: list[tuple[float, float]] | None = None,
        text: str = "",
    ) -> RenderSuccess | RenderError | DescribeSuccess | DescribeError | ShutdownConfirm:
    match type:
        case ResultType.RENDER_SUCCESS:
            if page_index is None:
                raise TypeError("Render results must include a page_index!")
            if image is None:
                raise TypeError("Render results must include image bytes!")
            return RenderSuccess(
                doc_uid=doc_uid,
                request_id=request_id,
                page_index=page_index,
                image=image,
                width=width,
                height=height,
                stride=stride,
                image_format=image_format,
                device_pixel_ratio=device_pixel_ratio,
            )
        case ResultType.RENDER_FAILURE:
            if page_index is None:
                raise TypeError("Render results must include a page_index!")
            return RenderError(
                doc_uid=doc_uid,
                request_id=request_id,
                page_index=page_index,
                text=text,
            )
        case ResultType.DESCRIBE_SUCCESS:
            return DescribeSuccess(
                doc_uid=doc_uid,
                request_id=request_id,
                title=title,
                page_sizes_pt=page_sizes_pt or [],
            )
        case ResultType.DESCRIBE_FAILURE:
            return DescribeError(
                doc_uid=doc_uid,
                request_id=request_id,
                text=text,
            )
        case ResultType.SHUTDOWN_CONFIRM:
            return ShutdownConfirm()
