from __future__ import annotations

import os
import statistics
import threading
import time
from dataclasses import dataclass

import cv2
import numpy as np
from paddleocr import PaddleOCR


@dataclass
class OcrResult:
    text: str
    confidence: float | None
    duration_ms: int
    line_count: int
    engine: str


_model: PaddleOCR | None = None
_model_lock = threading.Lock()
_predict_lock = threading.Lock()


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _build_model() -> PaddleOCR:
    # Mobile detection + multilingual Latin recognition provides a good CPU
    # balance for Portuguese municipal documents. The model lives for the life
    # of the container instead of being re-created per request/page.
    return PaddleOCR(
        lang=os.getenv("OCR_LANGUAGE", "pt"),
        ocr_version=os.getenv("OCR_VERSION", "PP-OCRv5"),
        text_detection_model_name=os.getenv("OCR_DETECTION_MODEL", "PP-OCRv5_mobile_det"),
        text_recognition_model_name=os.getenv("OCR_RECOGNITION_MODEL", "latin_PP-OCRv5_mobile_rec"),
        use_doc_orientation_classify=_env_bool("OCR_USE_DOC_ORIENTATION", False),
        use_doc_unwarping=_env_bool("OCR_USE_DOC_UNWARPING", False),
        use_textline_orientation=_env_bool("OCR_USE_TEXTLINE_ORIENTATION", False),
        device=os.getenv("OCR_DEVICE", "cpu"),
    )


def get_model() -> PaddleOCR:
    global _model
    if _model is not None:
        return _model
    with _model_lock:
        if _model is None:
            _model = _build_model()
    return _model


def _decode_image(data: bytes) -> np.ndarray:
    if not data:
        raise ValueError("Imagem vazia")
    encoded = np.frombuffer(data, dtype=np.uint8)
    image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    if image is None or image.size == 0:
        raise ValueError("Não foi possível decodificar a imagem")
    return image


def _extract_payload(result_item) -> dict:
    payload = getattr(result_item, "json", None)
    if callable(payload):
        payload = payload()
    if isinstance(payload, dict):
        return payload.get("res", payload)
    return {}


def recognize(data: bytes) -> OcrResult:
    started = time.perf_counter()
    image = _decode_image(data)
    model = get_model()

    # Paddle inference can use native threads internally. Serializing calls in
    # one model process avoids non-deterministic memory spikes; scale the service
    # horizontally (or run multiple containers) for higher throughput.
    with _predict_lock:
        predictions = list(model.predict(image))

    texts: list[str] = []
    scores: list[float] = []

    for prediction in predictions:
        payload = _extract_payload(prediction)
        raw_texts = payload.get("rec_texts")
        raw_scores = payload.get("rec_scores")
        if raw_texts is None:
            raw_texts = []
        if raw_scores is None:
            raw_scores = []

        for index, raw_text in enumerate(raw_texts):
            text = str(raw_text).strip()
            if not text:
                continue
            texts.append(text)
            if index < len(raw_scores):
                try:
                    score = float(raw_scores[index])
                    if np.isfinite(score):
                        scores.append(max(0.0, min(1.0, score)))
                except (TypeError, ValueError):
                    pass

    duration_ms = int((time.perf_counter() - started) * 1000)
    confidence = round(statistics.fmean(scores) * 100.0, 2) if scores else None

    return OcrResult(
        text="\n".join(texts).strip(),
        confidence=confidence,
        duration_ms=duration_ms,
        line_count=len(texts),
        engine="paddleocr-ppocrv5-mobile-latin",
    )
