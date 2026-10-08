# SIGED OCR Worker

Worker dedicado de OCR para retirar Tesseract/WASM das Vercel Functions.
Executa PaddleOCR localmente em um container; não usa LLM nem tokens de IA.

## Deploy

Este diretório é uma aplicação Docker independente. Pode ser usado em Railway,
Render, Google Cloud Run ou qualquer serviço que aceite Dockerfile.

Configure no serviço do worker:

- `OCR_API_KEY`: chave secreta longa e aleatória.
- `OCR_MAX_CONCURRENCY=2`: bom ponto inicial para 2-4 vCPU; use `1` em máquinas pequenas.
- demais variáveis do `.env.example` são opcionais.

O container pré-baixa os modelos PaddleOCR durante o build. O endpoint de saúde é:

`GET /health`

O endpoint usado pelo SIGED é:

`POST /v1/ocr/image`

Corpo: bytes PNG/JPEG. Cabeçalho: `Authorization: Bearer <OCR_API_KEY>`.

## Configuração no Vercel/SIGED

Adicione ao projeto Vercel:

- `OCR_PROVIDER=remote`
- `OCR_REMOTE_URL=https://SEU-WORKER.example.com`
- `OCR_REMOTE_API_KEY=<a mesma OCR_API_KEY do worker>`
- `OCR_REMOTE_TIMEOUT_MS=120000`
- `OCR_REMOTE_ATTEMPTS=2`
- `OCR_REMOTE_PAGE_CONCURRENCY=2`
- `OCR_PDF_BATCH_SIZE=8`

O SIGED continua detectando texto nativo no PDF. Somente páginas realmente
escaneadas são renderizadas e enviadas ao worker.

## Recursos sugeridos

Comece com pelo menos 2 vCPU e 4 GB RAM. Para PDFs grandes e múltiplos usuários,
4 vCPU / 8 GB RAM oferece folga maior. Escalabilidade deve ocorrer aumentando
instâncias do container; o processo Uvicorn fica com um worker para não duplicar
os modelos em memória dentro da mesma instância.
