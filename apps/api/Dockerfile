# MALAS API (mode hosting/BYOK) untuk Hugging Face Space (Docker) dan platform Docker mana pun.
# Build context = ROOT repo:  docker build -f apps/api/Dockerfile -t malas .
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
    MALAS_OUTPUT_DIR=/tmp/malas-output \
    # HF Space: 16 GB RAM di tier gratis, jadi pengambilan teks penuh PDF aman dinyalakan.
    MALAS_FULLTEXT=1 \
    # HF Space mengekspos app_port 7860 (README.md Space). Aplikasi membaca PORT.
    PORT=7860

RUN pip install --no-cache-dir uv

# Non-root dengan uid 1000 (yang diharapkan HF Spaces), dibuat SEBELUM instalasi dependensi: `chown -R` pada
# venv akan menggandakan layer (+1,4 GB). Folder tulis: /tmp/malas-output (hasil) dan /app/.cache (cache PDF).
RUN useradd --create-home --uid 1000 app \
    && mkdir -p /app/.cache /tmp/malas-output \
    && chown app:app /app /app/.cache /tmp/malas-output
USER app
WORKDIR /app

# Lapisan dependensi (di-cache selama pyproject.toml/uv.lock tidak berubah)
COPY --chown=app:app pyproject.toml uv.lock ./
COPY --chown=app:app packages/engine/pyproject.toml packages/engine/pyproject.toml
COPY --chown=app:app apps/api/pyproject.toml apps/api/pyproject.toml
RUN uv sync --frozen --no-dev --no-install-workspace --package malas-api

# Kode aplikasi (template .docx ikut di packages/engine/src/malas/templates)
COPY --chown=app:app packages/engine ./packages/engine
COPY --chown=app:app apps/api ./apps/api
RUN uv sync --frozen --no-dev --package malas-api

EXPOSE 7860
CMD ["malas-web"]
