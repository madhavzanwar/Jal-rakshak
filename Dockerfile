# One-container JalRakshak app: builds the React PWA, then serves it from the FastAPI backend.
# Used by docker-compose.yml (context = repo root).
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npx vite build

FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    JR_LLM_PROVIDER=auto OLLAMA_HOST=http://ollama:11434 \
    JR_CACHE_DIR=/app/backend/var/cache JR_DB_PATH=/app/backend/var/jalrakshak.db \
    JR_MODEL_DIR=/app/backend/models JR_FRONTEND_DIST=/app/frontend/dist
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app/backend
COPY backend/pyproject.toml ./
COPY backend/jalrakshak ./jalrakshak
COPY backend/models ./models
RUN pip install . "lightgbm>=4.3"
COPY --from=web /web/dist /app/frontend/dist
RUN useradd --create-home --uid 1000 jr && mkdir -p /app/backend/var && chown -R jr /app/backend/var
USER jr
VOLUME ["/app/backend/var"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)"
CMD ["uvicorn", "jalrakshak.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
