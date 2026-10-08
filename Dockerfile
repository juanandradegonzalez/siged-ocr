FROM python:3.10-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PADDLE_PDX_MODEL_SOURCE=BOS \
    OMP_NUM_THREADS=2 \
    MKL_NUM_THREADS=2

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./requirements.txt

# Keep the PaddleOCR 3.1 stack minimal. PaddleOCR 3.1.0's published
# metadata installs PaddleX extras for IE/multimodal/translation as well,
# which pulls LangChain and causes an incompatibility in PaddleX 3.1.x.
# Install only OCR-core, then install PaddleOCR itself without dependencies.
RUN python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install paddlepaddle==3.0.0 -i https://www.paddlepaddle.org.cn/packages/stable/cpu/ \
    && python -m pip install -r requirements.txt \
    && python -m pip install --no-deps paddleocr==3.1.0 \
    && python -m pip check

COPY app ./app

# Download OCR model assets at image build time so the first request avoids
# a multi-minute model-download cold start.
RUN OCR_API_KEY=build-preload python -m app.preload

ENV PORT=8080
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
  CMD curl -fsS http://127.0.0.1:${PORT}/health || exit 1

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1"]
