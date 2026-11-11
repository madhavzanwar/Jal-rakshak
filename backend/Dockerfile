# JalRakshak backend (FastAPI + agents). Build context is backend/:
#   docker build -t jalrakshak-api backend
# If a built frontend is copied/mounted at /app/frontend/dist it is served at "/".
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    JR_LLM_PROVIDER=auto \
    OLLAMA_HOST=http://ollama:11434

# libgomp1 is required by lightgbm (optional ML model)
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/backend
COPY pyproject.toml ./
COPY jalrakshak ./jalrakshak
COPY models ./models
RUN pip install . "lightgbm>=4.3"

RUN useradd --create-home --uid 1000 jr && mkdir -p /app/backend/var && chown -R jr /app/backend/var
USER jr

ENV JR_CACHE_DIR=/app/backend/var/cache \
    JR_DB_PATH=/app/backend/var/jalrakshak.db \
    JR_MODEL_DIR=/app/backend/models \
    JR_FRONTEND_DIST=/app/frontend/dist
VOLUME ["/app/backend/var"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)"
CMD ["uvicorn", "jalrakshak.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
