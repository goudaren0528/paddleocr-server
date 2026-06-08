from io import BytesIO
from unittest.mock import patch

from PIL import Image
from fastapi.testclient import TestClient

import server


class FakeDictLikeOCRResult:
    def __init__(self):
        self._data = {
            "rec_texts": ["hello"],
            "rec_scores": [0.9876],
            "rec_polys": [
                [[0, 0], [10, 0], [10, 10], [0, 10]],
            ],
        }

    def __contains__(self, key):
        return key in self._data

    def get(self, key, default=None):
        return self._data.get(key, default)


class FakeOCRRecordingCall:
    def __init__(self, result_factory=FakeDictLikeOCRResult):
        self.calls = []
        self.result_factory = result_factory

    def ocr(self, image_path, **kwargs):
        self.calls.append({"image_path": image_path, "kwargs": kwargs})
        return [self.result_factory()]


client = TestClient(server.app)


def make_png_bytes(width=32, height=16):
    buf = BytesIO()
    Image.new("RGB", (width, height), "white").save(buf, format="PNG")
    return buf.getvalue()


def test_ocr_endpoint_calls_paddleocr_without_runtime_kwargs():
    fake_ocr = FakeOCRRecordingCall(result_factory=lambda: {
        "rec_texts": ["hello"],
        "rec_scores": [0.9876],
        "rec_polys": [
            [[0, 0], [10, 0], [10, 10], [0, 10]],
        ],
    })

    with patch.object(server, "ocr_instance", fake_ocr):
        response = client.post(
            "/ocr",
            files={"file": ("sample.png", make_png_bytes(), "image/png")},
        )

    assert response.status_code == 200
    assert len(fake_ocr.calls) == 1
    assert fake_ocr.calls[0]["kwargs"] == {}
    assert response.json() == {
        "text": "hello",
        "lines": [
            {
                "text": "hello",
                "confidence": 0.9876,
                "box": [[0, 0], [10, 0], [10, 10], [0, 10]],
            }
        ],
    }


def test_ocr_endpoint_accepts_dict_like_ocr_results():
    fake_ocr = FakeOCRRecordingCall()

    with patch.object(server, "ocr_instance", fake_ocr):
        response = client.post(
            "/ocr",
            files={"file": ("sample.png", make_png_bytes(), "image/png")},
        )

    assert response.status_code == 200
    assert len(fake_ocr.calls) == 1
    assert fake_ocr.calls[0]["kwargs"] == {}
    assert response.json() == {
        "text": "hello",
        "lines": [
            {
                "text": "hello",
                "confidence": 0.9876,
                "box": [[0, 0], [10, 0], [10, 10], [0, 10]],
            }
        ],
    }


def test_ocr_endpoint_rejects_images_with_dimensions_over_limit():
    response = client.post(
        "/ocr",
        files={"file": ("huge.png", make_png_bytes(width=5000, height=100), "image/png")},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Image dimensions too large (max 4096x4096)"}


def test_ocr_endpoint_rejects_images_with_pixel_count_over_limit():
    response = client.post(
        "/ocr",
        files={"file": ("large.png", make_png_bytes(width=4000, height=4000), "image/png")},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Image pixel count too large (max 12MP)"}


def test_ocr_endpoint_rejects_invalid_image_payloads():
    response = client.post(
        "/ocr",
        files={"file": ("broken.png", b"not-a-real-image", "image/png")},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid or unsupported image file"}


def test_ocr_endpoint_logs_successful_runtime_metrics():
    fake_ocr = FakeOCRRecordingCall()

    with patch.object(server, "ocr_instance", fake_ocr), patch.object(server.logger, "info") as info_mock:
        response = client.post(
            "/ocr",
            files={"file": ("sample.png", make_png_bytes(), "image/png")},
        )

    assert response.status_code == 200
    assert info_mock.called
    log_message = info_mock.call_args[0][0]
    assert log_message.startswith("OCR completed in %.2f ms")


def test_ocr_endpoint_logs_failure_runtime_metrics():
    class FailingOCR:
        def ocr(self, image_path, **kwargs):
            raise RuntimeError("boom")

    with patch.object(server, "ocr_instance", FailingOCR()), patch.object(server.logger, "exception") as exc_mock:
        response = client.post(
            "/ocr",
            files={"file": ("sample.png", make_png_bytes(), "image/png")},
        )

    assert response.status_code == 500
    assert response.json() == {"detail": "boom"}
    assert exc_mock.called
    log_message = exc_mock.call_args[0][0]
    assert log_message.startswith("OCR failed after %.2f ms")


def test_ocr_endpoint_returns_empty_payload_when_no_text_detected():
    fake_ocr = FakeOCRRecordingCall(result_factory=lambda: {"rec_texts": [], "rec_scores": [], "rec_polys": []})

    with patch.object(server, "ocr_instance", fake_ocr), patch.object(server.logger, "info") as info_mock:
        response = client.post(
            "/ocr",
            files={"file": ("sample.png", make_png_bytes(), "image/png")},
        )

    assert response.status_code == 200
    assert response.json() == {"text": "", "lines": []}
    assert info_mock.called
