# KaTeX for server-side formula checks (app/modules/lessons/mathcheck.py). Pure JS: installed here, copied below.
FROM node:22-slim AS tools
WORKDIR /tools
COPY tools/package.json tools/package-lock.json ./
RUN npm ci --omit=dev --no-audit --no-fund

FROM python:3.11-slim

# Tesseract: OCR for scanned PDFs and images (PyMuPDF calls it). Node: runs tools/check_math.cjs.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng nodejs \
    && rm -rf /var/lib/apt/lists/*

# NODE_PATH outside /app: in development /app is the mounted source tree.
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 NODE_PATH=/opt/tools/node_modules
COPY --from=tools /tools/node_modules /opt/tools/node_modules
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
