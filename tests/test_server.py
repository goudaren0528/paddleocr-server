from unittest.mock import patch

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
            files={"file": ("sample.png", b"fake-image-bytes", "image/png")},
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
            files={"file": ("sample.png", b"fake-image-bytes", "image/png")},
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
