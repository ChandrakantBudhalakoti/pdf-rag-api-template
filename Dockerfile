# RAG Pipeline as a Service: API container.
#   docker build -t rag-pipeline-service .
#   docker run --env-file .env -p 8000:8000 rag-pipeline-service
# The database is NOT inside this image: point DATABASE_URL at PostgreSQL + pgvector.

FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # The package is used from /app/src (not pip-installed), so the project root is /app
    # and relative paths such as PDF_DIR=data/pdfs resolve inside the container.
    PYTHONPATH=/app/src

WORKDIR /app

# Dependencies first, so code changes don't reinstall them.
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY pyproject.toml ./
COPY src ./src
COPY evaluation ./evaluation
COPY data/pdfs ./data/pdfs

# Run as a non-root user; it only writes to data/pdfs (uploads) and evaluation/ (reports).
RUN useradd --create-home --uid 10001 app && chown -R app:app /app/data /app/evaluation
USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=3)"

# PORT is set by Cloud Run / App Runner; default 8000 locally.
CMD ["sh", "-c", "exec uvicorn rag_pipeline.api:app --host 0.0.0.0 --port ${PORT:-8000}"]
