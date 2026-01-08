# ══════════════════════════════════════════════════════════════════════════════
# FusionBot Dockerfile - Optimized for size and speed
# ══════════════════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────────────────────
# Stage 1: Builder - Install dependencies (cached layer)
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.13-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=0 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install build deps in single layer
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create venv and install deps (this layer is cached if requirements.txt unchanged)
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt /tmp/
# Install PyTorch CPU-only (sentence-transformers only needs torch, not torchvision/torchaudio)
# CPU-only PyTorch is ~800MB vs ~2GB for full PyTorch with CUDA
RUN pip install --upgrade pip wheel && \
    pip install torch --index-url https://download.pytorch.org/whl/cpu && \
    # Create requirements without torch (already installed)
    grep -v "^torch" /tmp/requirements.txt | grep -v "^#" | grep -v "^$" > /tmp/requirements_no_torch.txt && \
    pip install -r /tmp/requirements_no_torch.txt && \
    # Aggressive cleanup to reduce image size
    find /opt/venv -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true && \
    find /opt/venv -type f -name "*.pyc" -delete 2>/dev/null || true && \
    find /opt/venv -type f -name "*.pyo" -delete 2>/dev/null || true && \
    # Remove test files and docs from packages
    find /opt/venv -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true && \
    find /opt/venv -type d -name "test" -exec rm -rf {} + 2>/dev/null || true && \
    find /opt/venv -type d -name "__tests__" -exec rm -rf {} + 2>/dev/null || true && \
    find /opt/venv -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true && \
    find /opt/venv -type d -name "*.dist-info" -exec rm -rf {} + 2>/dev/null || true && \
    # Remove unnecessary PyTorch CUDA files (we only need CPU)
    find /opt/venv -path "*/torch/cuda*" -exec rm -rf {} + 2>/dev/null || true && \
    find /opt/venv -name "*cuda*" -type f -delete 2>/dev/null || true && \
    find /opt/venv -name "*nccl*" -type f -delete 2>/dev/null || true && \
    # Remove sentence-transformers cache and unnecessary models
    rm -rf /opt/venv/lib/python3.13/site-packages/sentence_transformers/cache 2>/dev/null || true && \
    # Remove transformers cache
    rm -rf /opt/venv/lib/python3.13/site-packages/transformers/.cache 2>/dev/null || true && \
    # Clean pip cache AFTER installation (saves space, cache already used for speed)
    pip cache purge 2>/dev/null || true && \
    # Remove pip build artifacts
    rm -rf /root/.cache/pip 2>/dev/null || true && \
    # Final size check
    du -sh /opt/venv

# ─────────────────────────────────────────────────────────────────────────────
# Stage 2: Production - Minimal runtime image
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.13-slim AS production

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Runtime deps only (libpq5 for postgres)
RUN apt-get update && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -g 1000 fusionbot \
    && useradd -u 1000 -g fusionbot -s /bin/bash -m fusionbot \
    && mkdir -p /app/data /app/logs

# Copy venv from builder
COPY --from=builder /opt/venv /opt/venv

# Copy app code
COPY --chown=fusionbot:fusionbot src/ /app/src/
COPY --chown=fusionbot:fusionbot main.py /app/

RUN chown -R fusionbot:fusionbot /app

USER fusionbot

HEALTHCHECK --interval=60s --timeout=10s --start-period=10s --retries=2 \
    CMD python -c "print('ok')" || exit 1

CMD ["python", "main.py"]
