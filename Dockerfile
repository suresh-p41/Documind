# DocuMind: one image serving the FastAPI backend and the built React
# dashboard on port 8080. Ollama is NOT in this image; it runs as its own
# pod (see deploy/) and is reached via OLLAMA_BASE_URL.

# ---------- Frontend build ----------
FROM node:20-slim AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---------- Backend ----------
FROM python:3.12-slim
# Shared libraries needed by Docling / RapidOCR (OpenCV)
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/requirements.txt .
# CPU-only PyTorch keeps the image much smaller (no CUDA wheels)
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt

COPY backend/app ./app
COPY --from=frontend /frontend/dist ./static

ENV STATIC_DIR=/app/static \
    OLLAMA_BASE_URL=http://ollama:11434 \
    PYTHONUNBUFFERED=1

EXPOSE 8080
CMD ["uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8080"]
