from __future__ import annotations

import asyncio
import os
import secrets
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from .ocr_engine import get_model, recognize


MAX_IMAGE_BYTES = max(1, int(os.getenv("OCR_MAX_IMAGE_BYTES", str(20 * 1024 * 1024))))
MAX_CONCURRENCY = max(1, int(os.getenv("OCR_MAX_CONCURRENCY", "2")))
_semaphore = asyncio.Semaphore(MAX_CONCURRENCY)


def _expected_api_key() -> str:
    value = os.getenv("OCR_API_KEY", "").strip()
    if not value:
        raise RuntimeError("OCR_API_KEY não configurada no worker")
    return value


def _authorize(authorization: str | None) -> None:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Authorization Bearer obrigatória")
    supplied = authorization.split(" ", 1)[1].strip()
    expected = _expected_api_key()
    if not secrets.compare_digest(supplied, expected):
        raise HTTPException(status_code=403, detail="Chave OCR inválida")


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Fail fast at startup if credentials/model setup is broken. The Docker
    # image also preloads model files during build, so this should be quick.
    _expected_api_key()
    await asyncio.to_thread(get_model)
    yield


app = FastAPI(title="SIGED OCR Worker", version="1.0.0", lifespan=lifespan)


@app.get("/health")
async def health():
    return {
        "ok": True,
        "engine": "paddleocr",
        "maxConcurrency": MAX_CONCURRENCY,
    }


@app.post("/v1/ocr/image")
async def ocr_image(
    request: Request,
    authorization: str | None = Header(default=None),
    x_request_id: str | None = Header(default=None),
):
    _authorize(authorization)

    content_type = (request.headers.get("content-type") or "").lower()
    if not (content_type.startswith("image/png") or content_type.startswith("image/jpeg") or content_type.startswith("image/jpg")):
        raise HTTPException(status_code=415, detail=f"Formato não suportado: {content_type or 'desconhecido'}")

    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail="Imagem vazia")
    if len(body) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail=f"Imagem excede o limite de {MAX_IMAGE_BYTES} bytes")

    request_id = x_request_id or str(uuid.uuid4())

    try:
        async with _semaphore:
            result = await asyncio.to_thread(recognize, body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        # Do not echo document text or raw bytes. Keep error diagnostic only.
        raise HTTPException(status_code=500, detail=f"Falha no motor OCR: {type(exc).__name__}: {exc}") from exc

    return JSONResponse({
        "requestId": request_id,
        "text": result.text,
        "confidence": result.confidence,
        "lineCount": result.line_count,
        "durationMs": result.duration_ms,
        "engine": result.engine,
    })
