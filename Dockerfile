FROM python:3.13-slim AS builder
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends gcc
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM python:3.13-slim
WORKDIR /app
RUN useradd --create-home appuser
COPY --from=builder /root/.local /home/appuser/.local
COPY --chown=appuser:appuser app/ ./app/
RUN mkdir -p /app/data /app/uploads /app/exports && chown -R appuser:appuser /app
ENV PATH=/home/appuser/.local/bin:$PATH PYTHONPATH=/app PYTHONUNBUFFERED=1
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${APP_PORT:-8000}/health')"
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${APP_PORT:-8000}"]
