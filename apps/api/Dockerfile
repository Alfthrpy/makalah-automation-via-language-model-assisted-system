# MALAS API (mode hosting/BYOK). Build context = ROOT repo:  docker build -f apps/api/Dockerfile .
# Dibuat untuk Render, tapi jalan di platform Docker mana pun.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH" \
    # Default aman untuk hosting publik: pengguna wajib membawa API key sendiri.
    MALAS_WEB_REQUIRE_KEY=1 \
    MALAS_WEB_HOST=0.0.0.0 \
    MALAS_OUTPUT_DIR=/tmp/malas-output

RUN pip install --no-cache-dir uv

WORKDIR /app

# Lapisan dependensi (di-cache selama pyproject.toml/uv.lock tidak berubah)
COPY pyproject.toml uv.lock ./
COPY packages/engine/pyproject.toml packages/engine/pyproject.toml
COPY apps/api/pyproject.toml apps/api/pyproject.toml
RUN uv sync --frozen --no-dev --no-install-workspace --package malas-api

# Kode aplikasi (template .docx ikut di packages/engine/src/malas/templates)
COPY packages/engine ./packages/engine
COPY apps/api ./apps/api
RUN uv sync --frozen --no-dev --package malas-api

# Jalan sebagai non-root; folder tulis: /tmp/malas-output (hasil) dan /app/.cache (cache PDF)
RUN useradd --create-home --uid 10001 app \
    && mkdir -p /tmp/malas-output /app/.cache \
    && chown -R app:app /app /tmp/malas-output
USER app

# Render menyuntikkan $PORT (default 10000); aplikasi membacanya sendiri.
EXPOSE 10000
CMD ["malas-web"]
