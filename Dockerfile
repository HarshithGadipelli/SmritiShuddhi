# =====================================================================
# SMRITI SHUDDHI - HUGGING FACE SPACES (UID 1000) & GOOGLE CLOUD RUN DOCKERFILE
# =====================================================================
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FORWARDED_ALLOW_IPS=* \
    HOST=0.0.0.0 \
    PORT=8080

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install CPU-only PyTorch to keep container lightweight and billing/free-tier compatible
RUN pip install --upgrade pip && \
    pip install --no-cache-dir "torch>=2.2.0" --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu -r /app/requirements.txt

# Copy project files (honoring .dockerignore; works cleanly both with local caches & clean Git clones)
COPY . /app

RUN mkdir -p /app/logs /app/artifacts/evaluation /app/data/qdrant_storage /app/static/uploads /app/sisa_adapters /app/models_cache

# Pre-cache bge-small-en-v1.5, deberta-v3-xsmall & initial SISA shards if not already baked in context
RUN python -m app.utils.preload_models

# Lock offline mode at runtime & grant non-root UID 1000 permissions (required by Hugging Face Spaces)
ENV HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    HOME=/home/user

RUN useradd -m -u 1000 user && \
    chown -R user:user /app

USER user

EXPOSE 8080

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1 --proxy-headers"]
