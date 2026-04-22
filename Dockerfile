# syntax=docker/dockerfile:1.7
# ARGOS backend · multi-stage Docker image
# - builder instala deps en /opt/venv
# - runtime copia el venv + código y corre uvicorn como non-root
# - Python 3.11 pineado (stack.md · alineación con SISMO V2)

# ─── Builder ─────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Compilación de wheels (bcrypt, cffi) requiere build-essential
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src/backend ./src/backend

RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install .

# ─── Runtime ─────────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

RUN groupadd --system argos \
    && useradd --system --gid argos --create-home --shell /usr/sbin/nologin argos

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /app/src/backend ./src/backend

USER argos

EXPOSE 8000

# Render inyecta $PORT · fallback a 8000 en local
CMD ["sh", "-c", "uvicorn argos.main:app --host 0.0.0.0 --port ${PORT:-8000} --app-dir src/backend --proxy-headers --forwarded-allow-ips '*'"]
