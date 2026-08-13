# syntax=docker/dockerfile:1
#
# Brain OS Enterprise Workflow Platform -- production image.
#
# Two stages: `builder` installs dependencies into a self-contained
# virtualenv (so build tools like gcc never end up in the final image),
# `runtime` copies just that venv plus the application code and runs as
# a non-root user.

FROM python:3.12-slim AS builder

WORKDIR /build

# chromadb and its transitive deps (onnxruntime, tokenizers, etc.) need a
# C/C++ toolchain to build any wheel that doesn't ship a prebuilt one for
# this platform.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt


# Test stage: same installed dependencies as `builder`, plus the test
# suite. Never part of the default build (the `runtime` stage below is
# last, so `docker build .` and `docker compose build` skip this one).
# Run explicitly with: docker build --target test -t brain-os:test .
FROM builder AS test

WORKDIR /app
COPY app ./app
COPY tests ./tests
COPY pytest.ini ./pytest.ini
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
CMD ["python", "-m", "pytest", "-v"]


FROM python:3.12-slim AS runtime

RUN groupadd --system brainos && useradd --system --gid brainos --create-home brainos

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY app ./app
COPY .env.example ./.env.example

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATABASE_PATH=/app/data/brain_os.db \
    CHECKPOINT_DB_PATH=/app/data/checkpoints.db \
    CHROMA_PERSIST_PATH=/app/data/chroma

# Data directory is created and owned by the non-root user up front so
# Settings.ensure_data_dir() never has to fall back to root-owned paths.
RUN mkdir -p /app/data && chown -R brainos:brainos /app

USER brainos

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health', timeout=3).status == 200 else 1)"

# Single worker by default: the app persists to SQLite, which is a
# single-writer store (see README "Known limitations" / PRODUCTION_READINESS.md).
# Scale out by moving to the Postgres checkpointer/repository backend
# described there before running multiple workers or replicas against
# the same data volume.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
