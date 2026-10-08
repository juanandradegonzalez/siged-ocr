# Como publicar o OCR sem programar

1. Crie um repositório novo no GitHub (por exemplo `siged-ocr`) e envie para ele todos os arquivos desta pasta.
2. Entre no Render, escolha **New > Blueprint** e conecte o repositório `siged-ocr`.
3. O Render lerá o arquivo `render.yaml` e criará o serviço Docker automaticamente.
4. Quando pedir `OCR_API_KEY`, informe uma senha/chave longa. Guarde essa mesma chave: ela será usada também na Vercel.
5. Aguarde o deploy. Quando ficar Online, copie a URL `https://...onrender.com`.
6. Abra `https://...onrender.com/health`. Deve retornar `ok: true` e `engine: paddleocr`.
7. No projeto SIGED da Vercel, em Settings > Environment Variables, adicione:
   - OCR_PROVIDER = remote
   - OCR_REMOTE_URL = URL do Render (sem barra final)
   - OCR_REMOTE_API_KEY = a mesma chave usada no Render
   - OCR_REMOTE_TIMEOUT_MS = 120000
   - OCR_REMOTE_ATTEMPTS = 2
   - OCR_REMOTE_PAGE_CONCURRENCY = 2
   - OCR_PDF_BATCH_SIZE = 8
8. Faça novo deploy da Vercel e teste um PDF digitalizado.
