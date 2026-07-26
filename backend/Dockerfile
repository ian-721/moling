FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN addgroup --system moling && adduser --system --ingroup moling moling

COPY requirements.txt ./
RUN python -m pip install --upgrade pip && \
    python -m pip install -r requirements.txt

COPY alembic.ini main.py docker-entrypoint.sh ./
COPY migrations ./migrations
COPY app ./app

RUN chmod 0555 /app/docker-entrypoint.sh && chown -R moling:moling /app
USER moling

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/readyz', timeout=3)"]

ENTRYPOINT ["/app/docker-entrypoint.sh"]
