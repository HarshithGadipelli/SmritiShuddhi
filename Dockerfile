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
    pip install --no-cache-dir "torch==2.14.1+cpu" --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Pre-download HuggingFace weights in an isolated cacheable layer BEFORE copying app code
COPY app/utils/preload_models.py /app/app/utils/preload_models.py
RUN mkdir -p /app/logs /app/artifacts/evaluation /app/data/qdrant_storage /app/static/uploads /app/sisa_adapters/partitions /app/models_cache && \
    python -c "import runpy; runpy.run_path('/app/app/utils/preload_models.py')['ensure_models_cached']()"

# Copy relatively static data & pre-trained SISA shard weights first so app/ edits reuse layer cache
COPY data /app/data
COPY sisa_adapters /app/sisa_adapters

# Copy remaining project files (honoring .dockerignore; works both with local caches & clean Git clones)
COPY . /app

# Materialize partition CSVs (<0.1s if .pt weights already exist) or train shards if missing
RUN python -c "import runpy; runpy.run_path('/app/app/utils/preload_models.py')['ensure_initial_sisa_shards']()"

# Lock offline mode at runtime & grant non-root UID 1000 permissions (required by Hugging Face Spaces)
ENV HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    HOME=/home/user

RUN useradd -m -u 1000 user && \
    chown -R user:user /app

USER user

EXPOSE 8080

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1 --proxy-headers"]
