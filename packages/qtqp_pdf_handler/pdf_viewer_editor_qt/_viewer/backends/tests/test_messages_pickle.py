import pickle

from pdf_viewer_editor_qt._viewer.backends._messages import (
    DescribeError,
    DescribeRequest,
    DescribeSuccess,
    RenderError,
    RenderRequest,
    RenderSuccess,
)


def test_render_job_is_picklable() -> None:
    msg = RenderRequest(
        request_id="r1",
        doc_uid="d1",
        doc_bytes=b"pdf",
        page_index=0,
        zoom=1.0,
        rotation_deg=0,
        target_dpi=144.0,
        device_pixel_ratio=1.0,
    )
    assert pickle.loads(pickle.dumps(msg)) == msg


def test_describe_job_is_picklable() -> None:
    msg = DescribeRequest(request_id="r1", doc_uid="d1", doc_bytes=b"pdf", title="t")
    assert pickle.loads(pickle.dumps(msg)) == msg


def test_results_are_picklable() -> None:
    msgs = [
        RenderSuccess(
            request_id="r1",
            doc_uid="d1",
            page_index=0,
            image=b"x",
            width=1,
            height=2,
            stride=4,
            image_format="RGBA",
            device_pixel_ratio=2.0,
        ),
        RenderError(request_id="r1", doc_uid="d1", page_index=0, text="nope"),
        DescribeSuccess(request_id="r2", doc_uid="d1", title="t", page_sizes_pt=[(1.0, 2.0)]),
        DescribeError(request_id="r2", doc_uid="d1", message="nope"),
    ]
    for msg in msgs:
        assert pickle.loads(pickle.dumps(msg)) == msg

